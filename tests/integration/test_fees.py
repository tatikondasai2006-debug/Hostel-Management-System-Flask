"""Fee generation/calculation integration tests."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.constants import FEE_OVERDUE, FEE_PARTIAL
from app.extensions import db
from app.models import StudentFee
from app.services import allocation_service, fee_service
from app.services.fee_service import FeeError

FUTURE_PERIOD = "2099-01"


def test_generate_fee_uses_room_base_fee(room, student, fee_structures):
    allocation_service.allocate_bed(student)
    fee = fee_service.generate_fee(student, FUTURE_PERIOD)

    assert fee.accommodation_amount == Decimal("4500.00")
    assert fee.mess_amount == Decimal("2500.00")
    assert fee.laundry_amount == Decimal("400.00")
    assert fee.maintenance_amount == Decimal("300.00")
    assert fee.total_amount == Decimal("7700.00")
    assert fee.room_id == room.id


def test_generate_fee_without_room_has_zero_accommodation(student, fee_structures):
    fee = fee_service.generate_fee(student, FUTURE_PERIOD)
    assert fee.accommodation_amount == Decimal("0.00")
    assert fee.total_amount == Decimal("0.00")


def test_generate_fee_falls_back_to_structure_when_base_fee_zero(
    hostel, make_room, make_student, fee_structures
):
    make_room(hostel, number="D-1", room_type="dormitory", capacity=4, fee="0")
    student = make_student()
    allocation_service.allocate_bed(student)
    fee = fee_service.generate_fee(student, FUTURE_PERIOD)
    assert fee.accommodation_amount == Decimal("2500.00")


def test_duplicate_period_raises(room, student, fee_structures):
    allocation_service.allocate_bed(student)
    fee_service.generate_fee(student, FUTURE_PERIOD)
    with pytest.raises(FeeError):
        fee_service.generate_fee(student, FUTURE_PERIOD)


def test_invalid_period_raises(room, student, fee_structures):
    allocation_service.allocate_bed(student)
    with pytest.raises(FeeError):
        fee_service.generate_fee(student, "2026-13")


def test_discount_reduces_total(room, student, fee_structures):
    allocation_service.allocate_bed(student)
    fee = fee_service.generate_fee(student, FUTURE_PERIOD, discount_amount="700.00")
    assert fee.total_amount == Decimal("7000.00")


def test_generate_fees_for_period_skips_existing(room, make_student, fee_structures):
    student_a = make_student()
    student_b = make_student()
    allocation_service.allocate_bed(student_a)
    allocation_service.allocate_bed(student_b)

    result = fee_service.generate_fees_for_period(FUTURE_PERIOD)
    assert len(result["created"]) == 2

    result2 = fee_service.generate_fees_for_period(FUTURE_PERIOD)
    assert len(result2["created"]) == 0
    assert len(result2["skipped"]) == 2


def test_apply_late_fees_adds_charge_and_marks_overdue(room, student, fee_structures):
    allocation_service.allocate_bed(student)
    fee = fee_service.generate_fee(student, FUTURE_PERIOD)
    assert fee.late_fee_amount == Decimal("0.00")

    fee.due_date = date.today() - timedelta(days=30)
    db.session.commit()

    changed = fee_service.apply_late_fees()
    db.session.refresh(fee)
    assert changed == 1
    assert fee.late_fee_amount == Decimal("154.00")
    assert fee.total_amount == Decimal("7854.00")
    assert fee.status == FEE_OVERDUE


def test_route_generate_fees(admin_client, room, make_student, fee_structures):
    student = make_student()
    allocation_service.allocate_bed(student)
    resp = admin_client.post(
        "/fees/generate",
        data={"billing_period": "2099-05", "scope": "active", "due_date": "2099-05-10"},
    )
    assert resp.status_code == 302
    fee = db.session.execute(
        db.select(StudentFee).where(StudentFee.billing_period == "2099-05")
    ).scalar_one()
    assert fee.student_id == student.id
    assert fee.status == FEE_PARTIAL or fee.status == "pending"
