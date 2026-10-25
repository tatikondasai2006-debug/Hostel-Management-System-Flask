"""Shared pytest fixtures.

The suite targets the dedicated ``TEST_DATABASE_URL`` database.  The schema is
built once per session (from the SQLAlchemy metadata plus the PostgreSQL
capacity trigger) and truncated between tests for isolation.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import text

from app import create_app
from app.constants import (
    ROLE_ADMIN,
    ROLE_STUDENT,
    ROOM_AVAILABLE,
    STUDENT_ACTIVE,
)
from app.extensions import db as _db
from app.models import Hostel, Room, Student, User
from config import TestingConfig

PG_CAPACITY_FUNCTION = """
CREATE OR REPLACE FUNCTION check_room_capacity()
RETURNS trigger AS $$
DECLARE
    room_capacity integer;
    bed_count integer;
BEGIN
    IF NEW.status <> 'active' THEN
        RETURN NEW;
    END IF;
    SELECT capacity INTO room_capacity FROM rooms WHERE id = NEW.room_id;
    IF room_capacity IS NULL THEN
        RETURN NEW;
    END IF;
    SELECT count(*) INTO bed_count
    FROM room_allocations
    WHERE room_id = NEW.room_id AND status = 'active' AND id <> COALESCE(NEW.id, -1);
    IF bed_count >= room_capacity THEN
        RAISE EXCEPTION 'Room % is at capacity', NEW.room_id USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

PG_CAPACITY_TRIGGER = """
CREATE TRIGGER trg_room_capacity
BEFORE INSERT OR UPDATE ON room_allocations
FOR EACH ROW EXECUTE FUNCTION check_room_capacity();
"""


def _build_schema() -> None:
    _db.session.remove()
    _db.drop_all()
    _db.create_all()
    if _db.engine.dialect.name == "postgresql":
        _db.session.execute(text(PG_CAPACITY_FUNCTION))
        _db.session.execute(text(PG_CAPACITY_TRIGGER))
        _db.session.commit()


def _truncate_all() -> None:
    _db.session.rollback()
    tables = [t.name for t in _db.metadata.sorted_tables]
    if not tables:
        return
    if _db.engine.dialect.name == "postgresql":
        cols = ", ".join(f'"{name}"' for name in tables)
        _db.session.execute(text(f"TRUNCATE {cols} RESTART IDENTITY CASCADE"))
    else:  # pragma: no cover - SQLite fallback
        for name in reversed(tables):
            _db.session.execute(text(f'DELETE FROM "{name}"'))
    _db.session.commit()


@pytest.fixture(scope="session")
def app():
    application = create_app(TestingConfig)
    with application.app_context():
        _build_schema()
    yield application


@pytest.fixture(autouse=True)
def _isolate(app):
    # A fresh application context per test keeps ``flask.g`` (and therefore
    # Flask-Login's cached ``current_user``) and the SQLAlchemy session from
    # leaking between tests.  The context stays pushed for the whole test so
    # the fixture helpers and the HTTP client share one session.
    with app.app_context():
        _db.session.remove()
        yield
        _db.session.rollback()
        _truncate_all()
        _db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Account fixtures
# ---------------------------------------------------------------------------
def _make_user(email: str, password: str, role: str) -> User:
    user = User(email=email, role=role, is_active=True)
    user.set_password(password)
    _db.session.add(user)
    _db.session.commit()
    return user


@pytest.fixture
def admin_user(app):
    return _make_user("admin@test.example", "AdminPass123", ROLE_ADMIN)


@pytest.fixture
def admin_client(client, admin_user):
    client.post(
        "/auth/login",
        data={"email": "admin@test.example", "password": "AdminPass123"},
    )
    return client


# ---------------------------------------------------------------------------
# Domain data fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def hostel(app) -> Hostel:
    hostel = Hostel(name="Test Hostel", address="1 Test Road")
    _db.session.add(hostel)
    _db.session.commit()
    return hostel


@pytest.fixture
def make_room(app):
    def _make(hostel: Hostel, number="A-1", room_type="double", capacity=2, fee="4500.00"):
        room = Room(
            hostel_id=hostel.id,
            room_number=number,
            floor=1,
            room_type=room_type,
            capacity=capacity,
            base_fee=Decimal(fee),
            status=ROOM_AVAILABLE,
        )
        _db.session.add(room)
        _db.session.commit()
        return room

    return _make


@pytest.fixture
def room(hostel, make_room) -> Room:
    return make_room(hostel, number="A-101", room_type="double", capacity=2)


@pytest.fixture
def make_student(app):
    _counter = {"n": 0}

    def _make(
        roll=None,
        name=None,
        status=STUDENT_ACTIVE,
        with_login=False,
        email=None,
        password="StudentPass123",
    ):
        _counter["n"] += 1
        n = _counter["n"]
        student = Student(
            full_name=name or f"Student {n}",
            email=email or f"student{n}@test.example",
            phone="9000000000",
            roll_number=roll or f"R{n:04d}",
            course="Computer Science",
            academic_year="1",
            status=status,
        )
        if with_login:
            user = User(email=student.email, role=ROLE_STUDENT, is_active=True)
            user.set_password(password)
            student.user = user
            _db.session.add(user)
        _db.session.add(student)
        _db.session.commit()
        return student

    return _make


@pytest.fixture
def student(make_student) -> Student:
    return make_student()


@pytest.fixture
def fee_structures(app):
    from app.services import fee_service

    fee_service.ensure_default_fee_structures()
