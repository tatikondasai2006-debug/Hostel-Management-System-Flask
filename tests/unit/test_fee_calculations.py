"""Unit tests for fee arithmetic (no database required)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.constants import FEE_OVERDUE, FEE_PAID, FEE_PARTIAL, FEE_PENDING
from app.models import StudentFee
from app.services import fee_service
from app.services.fee_service import FeeError


def _fee(**overrides) -> StudentFee:
    defaults = {
        "accommodation_amount": Decimal("0"),
        "mess_amount": Decimal("0"),
        "laundry_amount": Decimal("0"),
        "maintenance_amount": Decimal("0"),
        "other_amount": Decimal("0"),
        "discount_amount": Decimal("0"),
        "late_fee_amount": Decimal("0"),
        "total_amount": Decimal("0"),
        "amount_paid": Decimal("0"),
    }
    defaults.update(overrides)
    return StudentFee(**defaults)


def test_parse_period_valid():
    assert fee_service.parse_period("2026-04") == (2026, 4)


@pytest.mark.parametrize("value", ["2026-13", "2026/04", "abcd-01", "1999-01", "2101-01"])
def test_parse_period_invalid_raises(value):
    with pytest.raises(FeeError):
        fee_service.parse_period(value)


def test_default_due_date_uses_configured_day():
    assert fee_service.default_due_date("2026-02") == date(2026, 2, 10)


def test_default_due_date_clamps_to_month_end():
    assert fee_service.default_due_date("2026-02", due_day=31) == date(2026, 2, 28)
    assert fee_service.default_due_date("2024-02", due_day=31) == date(2024, 2, 29)


def test_period_bounds():
    assert fee_service.period_bounds("2026-02") == (date(2026, 2, 1), date(2026, 2, 28))


def test_base_total_sums_components():
    fee = _fee(
        accommodation_amount=Decimal("100"),
        mess_amount=Decimal("50"),
        laundry_amount=Decimal("10"),
        maintenance_amount=Decimal("5"),
        other_amount=Decimal("2"),
    )
    assert fee_service.base_total(fee) == Decimal("167.00")


def test_base_total_subtracts_discount():
    fee = _fee(accommodation_amount=Decimal("100"), discount_amount=Decimal("30"))
    assert fee_service.base_total(fee) == Decimal("70.00")


def test_base_total_clamps_discount_to_subtotal():
    fee = _fee(accommodation_amount=Decimal("100"), discount_amount=Decimal("500"))
    assert fee_service.base_total(fee) == Decimal("0.00")
    assert fee.discount_amount == Decimal("100")


def test_late_fee_zero_within_grace_period():
    fee = _fee(
        accommodation_amount=Decimal("1000"),
        due_date=date.today() - timedelta(days=2),
    )
    assert fee_service.compute_late_fee(fee, Decimal("2"), 5) == Decimal("0.00")


def test_late_fee_applied_after_grace_period():
    fee = _fee(
        accommodation_amount=Decimal("1000"),
        due_date=date.today() - timedelta(days=30),
    )
    assert fee_service.compute_late_fee(fee, Decimal("2"), 5) == Decimal("20.00")


def test_late_fee_uses_outstanding_balance():
    fee = _fee(
        accommodation_amount=Decimal("1000"),
        amount_paid=Decimal("400"),
        due_date=date.today() - timedelta(days=30),
    )
    assert fee_service.compute_late_fee(fee, Decimal("2"), 5) == Decimal("12.00")


def test_late_fee_zero_when_fully_paid():
    fee = _fee(
        accommodation_amount=Decimal("1000"),
        amount_paid=Decimal("1000"),
        due_date=date.today() - timedelta(days=30),
    )
    assert fee_service.compute_late_fee(fee, Decimal("2"), 5) == Decimal("0.00")


def test_refresh_status_pending():
    fee = _fee(total_amount=Decimal("100"), due_date=date.today() + timedelta(days=10))
    assert fee_service.refresh_status(fee) == FEE_PENDING


def test_refresh_status_partial():
    fee = _fee(
        total_amount=Decimal("100"),
        amount_paid=Decimal("40"),
        due_date=date.today() + timedelta(days=10),
    )
    assert fee_service.refresh_status(fee) == FEE_PARTIAL


def test_refresh_status_overdue():
    fee = _fee(total_amount=Decimal("100"), due_date=date.today() - timedelta(days=1))
    assert fee_service.refresh_status(fee) == FEE_OVERDUE


def test_refresh_status_paid():
    fee = _fee(total_amount=Decimal("100"), amount_paid=Decimal("100"))
    assert fee_service.refresh_status(fee) == FEE_PAID
