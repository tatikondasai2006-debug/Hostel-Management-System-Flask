"""Fee calculation and billing service.

Billing rules (documented, deterministic)
-----------------------------------------
* ``billing_period`` is ``YYYY-MM``.
* Accommodation amount: the room's own ``base_fee`` when greater than zero,
  otherwise the ``FeeStructure.monthly_amount`` for the room's type.
* Mess / laundry / maintenance come from the ``FeeStructure`` for the room
  type and can be overridden per generated bill.
* ``subtotal`` = accommodation + mess + laundry + maintenance + other
* ``net_before_late`` = subtotal - discount  (discount is clamped to subtotal)
* Late fee (only while an overdue balance exists)::

      outstanding = net_before_late - amount_paid
      late_fee    = round_half_up(max(outstanding, 0) * percent / 100, 2)

* ``total_amount`` = net_before_late + late_fee
* ``balance`` = total_amount - amount_paid

All arithmetic uses :class:`decimal.Decimal` with ``ROUND_HALF_UP`` to 2
places.  Binary floating point is never used for money.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.constants import (
    FEE_OVERDUE,
    FEE_PAID,
    FEE_PARTIAL,
    FEE_PENDING,
    ROOM_DORMITORY,
    ROOM_DOUBLE,
    ROOM_SINGLE,
    ROOM_TYPES,
    STUDENT_ACTIVE,
)
from app.extensions import db
from app.models import FeeStructure, Student, StudentFee
from app.services import settings_service
from app.utils.money import money, to_decimal

DEFAULT_DUE_DAY = 10

DEFAULT_FEE_STRUCTURES = {
    ROOM_SINGLE: {
        "monthly_amount": Decimal("6500.00"),
        "mess_amount": Decimal("2500.00"),
        "laundry_amount": Decimal("400.00"),
        "maintenance_amount": Decimal("300.00"),
    },
    ROOM_DOUBLE: {
        "monthly_amount": Decimal("4500.00"),
        "mess_amount": Decimal("2500.00"),
        "laundry_amount": Decimal("400.00"),
        "maintenance_amount": Decimal("300.00"),
    },
    ROOM_DORMITORY: {
        "monthly_amount": Decimal("2500.00"),
        "mess_amount": Decimal("2500.00"),
        "laundry_amount": Decimal("400.00"),
        "maintenance_amount": Decimal("300.00"),
    },
}


class FeeError(Exception):
    """Raised for invalid fee operations."""


# ---------------------------------------------------------------------------
# Fee structures
# ---------------------------------------------------------------------------
def ensure_default_fee_structures(commit: bool = True) -> list[FeeStructure]:
    """Create missing per-room-type fee structures with sensible defaults."""
    created = []
    for room_type in ROOM_TYPES:
        existing = db.session.execute(
            select(FeeStructure).where(FeeStructure.room_type == room_type)
        ).scalar_one_or_none()
        if existing is None:
            defaults = DEFAULT_FEE_STRUCTURES[room_type]
            structure = FeeStructure(room_type=room_type, **defaults)
            db.session.add(structure)
            created.append(structure)
    if created and commit:
        db.session.commit()
    return created


def get_structure(room_type: str | None) -> FeeStructure | None:
    if not room_type:
        return None
    return db.session.execute(
        select(FeeStructure).where(FeeStructure.room_type == room_type)
    ).scalar_one_or_none()


def parse_period(billing_period: str) -> tuple[int, int]:
    try:
        year_str, month_str = billing_period.split("-")
        year, month = int(year_str), int(month_str)
        if not (1 <= month <= 12) or year < 2000 or year > 2100:
            raise ValueError
        return year, month
    except (ValueError, AttributeError):
        raise FeeError("Billing period must be in the format YYYY-MM.") from None


def period_bounds(billing_period: str) -> tuple[date, date]:
    year, month = parse_period(billing_period)
    start = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end = date(year, month, last_day)
    return start, end


def default_due_date(billing_period: str, due_day: int = DEFAULT_DUE_DAY) -> date:
    year, month = parse_period(billing_period)
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(due_day, last_day))


def overdue_cutoff(grace_days: int) -> date:
    return date.today() - timedelta(days=grace_days)


# ---------------------------------------------------------------------------
# Calculation
# ---------------------------------------------------------------------------
def base_total(fee: StudentFee) -> Decimal:
    subtotal = (
        to_decimal(fee.accommodation_amount)
        + to_decimal(fee.mess_amount)
        + to_decimal(fee.laundry_amount)
        + to_decimal(fee.maintenance_amount)
        + to_decimal(fee.other_amount)
    )
    discount = to_decimal(fee.discount_amount)
    if discount > subtotal:
        discount = subtotal
        fee.discount_amount = discount
    return money(subtotal - discount)


def compute_late_fee(fee: StudentFee, percent: Decimal, grace_days: int) -> Decimal:
    """Late fee applies only after the grace period and only to the balance."""
    if not fee.due_date or percent <= 0:
        return Decimal("0.00")
    if date.today() <= fee.due_date + timedelta(days=grace_days):
        return Decimal("0.00")
    outstanding = base_total(fee) - to_decimal(fee.amount_paid)
    if outstanding <= 0:
        return Decimal("0.00")
    return money(outstanding * to_decimal(percent) / Decimal("100"))


def recompute_totals(
    fee: StudentFee, percent: Decimal | None = None, grace: int | None = None
) -> StudentFee:
    if percent is None or grace is None:
        policy_percent, policy_grace = settings_service.get_late_fee_policy()
        percent = policy_percent if percent is None else percent
        grace = policy_grace if grace is None else grace
    fee.discount_amount = money(to_decimal(fee.discount_amount))
    fee.late_fee_amount = compute_late_fee(fee, percent, grace)
    fee.total_amount = money(base_total(fee) + fee.late_fee_amount)
    fee.amount_paid = money(to_decimal(fee.amount_paid))
    refresh_status(fee)
    return fee


def refresh_status(fee: StudentFee, today: date | None = None) -> str:
    today = today or date.today()
    balance = to_decimal(fee.total_amount) - to_decimal(fee.amount_paid)
    if balance <= 0:
        fee.status = FEE_PAID
    elif fee.due_date and fee.due_date < today:
        fee.status = FEE_OVERDUE
    elif to_decimal(fee.amount_paid) > 0:
        fee.status = FEE_PARTIAL
    else:
        fee.status = FEE_PENDING
    return fee.status


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
def accommodation_amount_for(student: Student) -> tuple[Decimal, StudentFee | None, object]:
    """Return (amount, room, structure) for a student's current room."""
    room = student.current_room
    if room is None:
        return Decimal("0.00"), None, None
    structure = get_structure(room.room_type)
    base_fee = to_decimal(room.base_fee)
    amount = base_fee if base_fee > 0 else to_decimal(structure.monthly_amount if structure else 0)
    return amount, room, structure


def generate_fee(
    student: Student,
    billing_period: str,
    due_date: date | None = None,
    other_amount: Decimal | int | float | str = 0,
    discount_amount=0,
    notes: str | None = None,
    commit: bool = True,
) -> StudentFee:
    """Generate (and persist) a monthly bill for ``student``.

    Raises :class:`FeeError` if a bill already exists for the period.
    """
    parse_period(billing_period)  # validate early
    existing = db.session.execute(
        select(StudentFee).where(
            StudentFee.student_id == student.id,
            StudentFee.billing_period == billing_period,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise FeeError(f"A fee record for {billing_period} already exists for this student.")

    accommodation, room, structure = accommodation_amount_for(student)
    fee = StudentFee(
        student_id=student.id,
        fee_structure_id=structure.id if structure else None,
        room_id=room.id if room else None,
        billing_period=billing_period,
        room_type=room.room_type if room else None,
        accommodation_amount=money(accommodation),
        mess_amount=money(structure.mess_amount if structure else 0),
        laundry_amount=money(structure.laundry_amount if structure else 0),
        maintenance_amount=money(structure.maintenance_amount if structure else 0),
        other_amount=money(other_amount),
        discount_amount=money(discount_amount),
        due_date=due_date or default_due_date(billing_period),
        notes=notes,
    )
    recompute_totals(fee)
    db.session.add(fee)
    if commit:
        try:
            db.session.commit()
        except IntegrityError as exc:
            db.session.rollback()
            raise FeeError(
                f"A fee record for {billing_period} already exists for this student."
            ) from exc
    return fee


def generate_fees_for_period(
    billing_period: str,
    due_date: date | None = None,
    student_ids: list[int] | None = None,
    only_active: bool = True,
    commit: bool = True,
) -> dict:
    """Bulk-generate bills for all (or selected) students for a period."""
    parse_period(billing_period)
    stmt = select(Student)
    if student_ids:
        stmt = stmt.where(Student.id.in_(student_ids))
    elif only_active:
        stmt = stmt.where(Student.status == STUDENT_ACTIVE)
    students = db.session.execute(stmt).scalars().all()

    created, skipped = [], []
    for student in students:
        try:
            fee = generate_fee(student, billing_period, due_date=due_date, commit=False)
            created.append(fee)
        except FeeError:
            skipped.append(student)
    if commit:
        db.session.commit()
    return {"created": created, "skipped": skipped, "period": billing_period}


def apply_late_fees(commit: bool = True) -> int:
    """Recompute late fees + statuses for every unpaid bill."""
    percent, grace = settings_service.get_late_fee_policy()
    fees = (
        db.session.execute(
            select(StudentFee).where(StudentFee.amount_paid < StudentFee.total_amount)
        )
        .scalars()
        .all()
    )
    changed = 0
    for fee in fees:
        before = (fee.late_fee_amount, fee.status)
        recompute_totals(fee, percent, grace)
        if (fee.late_fee_amount, fee.status) != before:
            changed += 1
    if commit:
        db.session.commit()
    return changed


def mark_overdue_fees(commit: bool = True) -> int:
    percent, grace = settings_service.get_late_fee_policy()
    fees = (
        db.session.execute(
            select(StudentFee).where(StudentFee.amount_paid < StudentFee.total_amount)
        )
        .scalars()
        .all()
    )
    changed = 0
    for fee in fees:
        recompute_totals(fee, percent, grace)
        changed += 1
    if commit:
        db.session.commit()
    return changed


def active_student_ids() -> list[int]:
    return list(
        db.session.execute(select(Student.id).where(Student.status == STUDENT_ACTIVE)).scalars()
    )
