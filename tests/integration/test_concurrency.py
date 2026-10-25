"""PostgreSQL-specific concurrency and trigger tests.

These tests exercise the row-locking allocation strategy and the database
capacity trigger, so they only run against PostgreSQL (SQLite ignores
``FOR UPDATE``).
"""

import threading

import pytest
from sqlalchemy import func, select, text

from app.constants import ALLOCATION_ACTIVE
from app.extensions import db
from app.models import RoomAllocation, Student
from app.services import allocation_service


@pytest.fixture
def pg_required(app):
    if db.engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL is required for locking/trigger semantics")


def test_capacity_trigger_blocks_direct_overfill(app, pg_required, room, make_student):
    first = make_student()
    second = make_student()
    allocation_service.allocate_bed(first)
    allocation_service.allocate_bed(second)

    third = make_student()
    with pytest.raises(Exception) as excinfo:
        db.session.execute(
            text(
                "INSERT INTO room_allocations "
                "(student_id, room_id, bed_index, status, allocated_at) "
                "VALUES (:s, :r, 3, 'active', now())"
            ),
            {"s": third.id, "r": room.id},
        )
        db.session.commit()
    assert "capacity" in str(excinfo.value).lower()
    db.session.rollback()


def test_concurrent_allocation_never_overfills(app, pg_required, hostel, make_room, make_student):
    room = make_room(hostel, number="C-1", room_type="dormitory", capacity=3)
    student_ids = [make_student().id for _ in range(6)]

    results: list[str] = []
    lock = threading.Lock()

    def worker(student_id: int) -> None:
        with app.app_context():
            student = db.session.get(Student, student_id)
            try:
                allocation_service.allocate_bed(student)
                outcome = "ok"
            except allocation_service.AllocationError:
                outcome = "no-capacity"
            finally:
                db.session.remove()
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=worker, args=(sid,)) for sid in student_ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results.count("ok") == 3
    db.session.rollback()
    active = db.session.execute(
        select(func.count())
        .select_from(RoomAllocation)
        .where(
            RoomAllocation.room_id == room.id,
            RoomAllocation.status == ALLOCATION_ACTIVE,
        )
    ).scalar_one()
    assert active == 3
