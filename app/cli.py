"""Custom Flask CLI commands.

Secure administrative bootstrap and development helpers live here so that no
administrator password is ever hard-coded in the repository.
"""

from __future__ import annotations

import contextlib
import os
from datetime import date, timedelta
from decimal import Decimal

import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy import select

from app.constants import (
    ROLE_ADMIN,
    ROOM_AVAILABLE,
    STUDENT_ACTIVE,
)
from app.extensions import db
from app.models import (
    Hostel,
    Room,
    Student,
    StudentFee,
    User,
)
from app.services import allocation_service, fee_service, settings_service


def _validate_password(password: str) -> None:
    if len(password) < 10:
        raise click.ClickException("Admin password must be at least 10 characters.")
    if password.lower() in {"password", "admin12345", "changeme"}:
        raise click.ClickException("Admin password is too common.")


@click.command("bootstrap-admin")
@click.option("--email", default=None, help="Admin email (or ADMIN_EMAIL env).")
@click.option("--password", default=None, help="Admin password (or ADMIN_PASSWORD env).")
@click.option("--name", default=None, help="Display name (or ADMIN_NAME env).")
@with_appcontext
def bootstrap_admin(email, password, name):
    """Create the initial administrator account (idempotent)."""
    email = (email or os.environ.get("ADMIN_EMAIL") or "").strip().lower()
    password = password or os.environ.get("ADMIN_PASSWORD")
    name = (name or os.environ.get("ADMIN_NAME") or "System Administrator").strip()

    if not email or not password:
        raise click.ClickException(
            "Provide --email/--password or set ADMIN_EMAIL / ADMIN_PASSWORD. "
            "No default administrator credentials are shipped."
        )
    _validate_password(password)

    user = db.session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is not None:
        if user.role != ROLE_ADMIN:
            raise click.ClickException(f"A non-admin account already uses {email}.")
        user.set_password(password)
        db.session.commit()
        click.echo(f"Updated password for existing administrator {email}.")
        return

    user = User(email=email, role=ROLE_ADMIN, is_active=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo(f"Created administrator {email} ({name}).")


@click.command("seed-defaults")
@with_appcontext
def seed_defaults():
    """Create default fee structures and settings (idempotent)."""
    created = fee_service.ensure_default_fee_structures(commit=False)
    for key, value in settings_service.DEFAULT_SETTINGS.items():
        settings_service.set_setting(key, value)
    db.session.commit()
    click.echo(f"Fee structures created: {len(created)}. Settings ensured.")


@click.command("generate-fees")
@click.option("--period", required=True, help="Billing period YYYY-MM")
@click.option("--due-day", default=fee_service.DEFAULT_DUE_DAY, type=int)
@with_appcontext
def generate_fees(period, due_day):
    """Generate monthly bills for all active students."""
    result = fee_service.generate_fees_for_period(period, due_day=due_day)
    click.echo(
        f"Period {period}: {len(result['created'])} created, {len(result['skipped'])} skipped."
    )


@click.command("apply-late-fees")
@with_appcontext
def apply_late_fees():
    """Recompute late fees and statuses on all unpaid bills."""
    changed = fee_service.apply_late_fees()
    click.echo(f"Updated {changed} fee records.")


@click.command("seed-demo")
@click.confirmation_option(prompt="Seed demo data? This is for development only.")
@with_appcontext
def seed_demo():
    """Populate a development dataset (refuses to run in production)."""
    if current_app.config.get("ENV") == "production":
        raise click.ClickException("Refusing to seed demo data in production.")

    fee_service.ensure_default_fee_structures(commit=False)
    settings_service.set_setting("hostel_name", "Sunrise Student Hostel")
    db.session.commit()

    hostels = {}
    for name, address in [
        ("Aryabhata Boys Hostel", "North Campus, Block A"),
        ("Kalpana Girls Hostel", "South Campus, Block C"),
    ]:
        hostel = db.session.execute(select(Hostel).where(Hostel.name == name)).scalar_one_or_none()
        if hostel is None:
            hostel = Hostel(name=name, address=address)
            db.session.add(hostel)
        hostels[name] = hostel
    db.session.flush()

    room_specs = [
        ("Aryabhata Boys Hostel", "A-101", 1, "single", 1, Decimal("6500")),
        ("Aryabhata Boys Hostel", "A-102", 1, "double", 2, Decimal("4500")),
        ("Aryabhata Boys Hostel", "A-103", 1, "double", 2, Decimal("4500")),
        ("Aryabhata Boys Hostel", "A-201", 2, "dormitory", 4, Decimal("2500")),
        ("Kalpana Girls Hostel", "C-101", 1, "single", 1, Decimal("7000")),
        ("Kalpana Girls Hostel", "C-102", 1, "double", 2, Decimal("4800")),
        ("Kalpana Girls Hostel", "C-201", 2, "dormitory", 6, Decimal("2600")),
    ]
    rooms = []
    for hostel_name, number, floor, rtype, capacity, fee in room_specs:
        existing = db.session.execute(
            select(Room).where(
                Room.hostel_id == hostels[hostel_name].id, Room.room_number == number
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = Room(
                hostel_id=hostels[hostel_name].id,
                room_number=number,
                floor=floor,
                room_type=rtype,
                capacity=capacity,
                base_fee=fee,
                status=ROOM_AVAILABLE,
                amenities="Wi-Fi, Study desk, Fan",
            )
            db.session.add(existing)
        rooms.append(existing)
    db.session.commit()

    demo_students = [
        (
            "Aarav Sharma",
            "aarav@student.example",
            "9000000001",
            "CS2025001",
            "B.Tech Computer Science",
            "1",
            "Aryabhata Boys Hostel",
        ),
        (
            "Diya Patel",
            "diya@student.example",
            "9000000002",
            "CS2025002",
            "B.Tech Computer Science",
            "1",
            "Kalpana Girls Hostel",
        ),
        (
            "Rohan Verma",
            "rohan@student.example",
            "9000000003",
            "ME2025001",
            "B.Tech Mechanical",
            "1",
            "Aryabhata Boys Hostel",
        ),
        (
            "Ananya Nair",
            "ananya@student.example",
            "9000000004",
            "EC2025001",
            "B.Tech Electronics",
            "2",
            "Kalpana Girls Hostel",
        ),
        (
            "Kabir Singh",
            "kabir@student.example",
            "9000000005",
            "CS2025003",
            "B.Tech Computer Science",
            "2",
            "Aryabhata Boys Hostel",
        ),
        (
            "Isha Reddy",
            "isha@student.example",
            "9000000006",
            "BM2025001",
            "BBA",
            "2",
            "Kalpana Girls Hostel",
        ),
    ]
    created_students = []
    for name, email, phone, roll, course, year, _hostel in demo_students:
        existing = db.session.execute(
            select(Student).where(Student.roll_number == roll)
        ).scalar_one_or_none()
        if existing is None:
            student = Student(
                full_name=name,
                email=email,
                phone=phone,
                roll_number=roll,
                course=course,
                academic_year=year,
                admission_date=date.today() - timedelta(days=120),
                status=STUDENT_ACTIVE,
                emergency_contact="9000000099",
                address="123 Demo Street",
            )
            db.session.add(student)
            created_students.append(student)
    db.session.commit()

    for student in created_students:
        with contextlib.suppress(allocation_service.AllocationError):
            allocation_service.allocate_bed(student, notes="demo allocation")

    period = date.today().strftime("%Y-%m")
    fee_service.generate_fees_for_period(period)
    for student in created_students:
        fee = (
            db.session.execute(select(StudentFee).where(StudentFee.student_id == student.id))
            .scalars()
            .first()
        )
        if fee is None:
            continue
        from app.services import payment_service

        with contextlib.suppress(payment_service.PaymentError):
            payment_service.record_payment(fee, fee.total_amount, "cash", notes="demo payment")

    click.echo("Demo data seeded (development only).")


ALL_COMMANDS = [
    bootstrap_admin,
    seed_defaults,
    generate_fees,
    apply_late_fees,
    seed_demo,
]


def register_cli(app) -> None:
    for command in ALL_COMMANDS:
        app.cli.add_command(command)
