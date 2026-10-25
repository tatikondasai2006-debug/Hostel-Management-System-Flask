"""Allocation service and route integration tests."""

import pytest
from sqlalchemy import func, select

from app.constants import ALLOCATION_ACTIVE, ALLOCATION_RELEASED
from app.extensions import db
from app.models import RoomAllocation
from app.services import allocation_service


def _active_count(room_id: int) -> int:
    return db.session.execute(
        select(func.count())
        .select_from(RoomAllocation)
        .where(
            RoomAllocation.room_id == room_id,
            RoomAllocation.status == ALLOCATION_ACTIVE,
        )
    ).scalar_one()


def test_auto_allocate_assigns_lowest_free_bed(room, student):
    allocation = allocation_service.allocate_bed(student)
    assert allocation.room_id == room.id
    assert allocation.bed_index == 1
    assert allocation.status == ALLOCATION_ACTIVE
    assert student.current_room.id == room.id


def test_allocations_fill_room_then_fail(room, make_student):
    first = make_student()
    second = make_student()
    third = make_student()

    allocation_service.allocate_bed(first)
    allocation_service.allocate_bed(second)
    assert _active_count(room.id) == 2

    with pytest.raises(allocation_service.NoCapacityError):
        allocation_service.allocate_bed(third)


def test_lowest_free_bed_reused_after_release(room, make_student):
    first = make_student()
    second = make_student()
    a1 = allocation_service.allocate_bed(first)
    allocation_service.allocate_bed(second)
    allocation_service.release_allocation(a1)

    third = make_student()
    a3 = allocation_service.allocate_bed(third)
    assert a3.bed_index == 1


def test_inactive_student_cannot_be_allocated(room, make_student):
    from app.constants import STUDENT_INACTIVE

    student = make_student(status=STUDENT_INACTIVE)
    with pytest.raises(allocation_service.AllocationError):
        allocation_service.allocate_bed(student)


def test_double_allocation_same_student_fails(room, make_student):
    student = make_student()
    allocation_service.allocate_bed(student)
    with pytest.raises(allocation_service.AllocationError):
        allocation_service.allocate_bed(student)


def test_release_allocation_is_idempotent(room, student):
    allocation = allocation_service.allocate_bed(student)
    allocation_service.release_allocation(allocation, reason="checkout")
    assert allocation.status == ALLOCATION_RELEASED
    allocation_service.release_allocation(allocation)
    assert allocation.status == ALLOCATION_RELEASED
    assert room.available_beds == room.capacity


def test_transfer_moves_student_and_frees_old_room(hostel, make_room, make_student):
    room_a = make_room(hostel, number="A-1", room_type="double", capacity=2)
    room_b = make_room(hostel, number="B-1", room_type="double", capacity=2)
    student = make_student()

    original = allocation_service.allocate_bed(student)
    assert original.room_id == room_a.id

    moved = allocation_service.transfer_student(student, room_b.id)
    assert moved.room_id == room_b.id
    assert student.current_room.id == room_b.id
    assert _active_count(room_a.id) == 0
    assert _active_count(room_b.id) == 1


def test_transfer_to_same_room_rejected(room, student):
    allocation_service.allocate_bed(student)
    with pytest.raises(allocation_service.AllocationError):
        allocation_service.transfer_student(student, room.id)


def test_preferred_room_is_honoured(hostel, make_room, make_student):
    preferred = make_room(hostel, number="Z-9", room_type="double", capacity=2)
    make_room(hostel, number="A-1", room_type="double", capacity=2)
    student = make_student()
    allocation = allocation_service.allocate_bed(student, preferred_room_id=preferred.id)
    assert allocation.room_id == preferred.id


def test_route_auto_allocate(admin_client, room, make_student):
    student = make_student()
    resp = admin_client.post(
        "/allocations/new",
        data={"student_id": student.id, "room_type": "", "notes": ""},
    )
    assert resp.status_code == 302
    db.session.refresh(student)
    assert student.current_allocation is not None


def test_route_release(admin_client, room, make_student):
    student = make_student()
    allocation = allocation_service.allocate_bed(student)
    resp = admin_client.post(f"/allocations/{allocation.id}/release", data={"reason": "checkout"})
    assert resp.status_code == 302
    db.session.refresh(allocation)
    assert allocation.status == ALLOCATION_RELEASED
