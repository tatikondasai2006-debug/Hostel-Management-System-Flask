"""Payment recording/reversal integration tests."""

from decimal import Decimal

import pytest

from app.constants import FEE_PAID, FEE_PARTIAL
from app.extensions import db
from app.services import allocation_service, fee_service, payment_service
from app.services.payment_service import OverpaymentError, PaymentError

FUTURE_PERIOD = "2099-02"


@pytest.fixture
def fee(room, student, fee_structures):
    allocation_service.allocate_bed(student)
    return fee_service.generate_fee(student, FUTURE_PERIOD)


def test_record_payment_updates_balance_and_status(fee):
    payment = payment_service.record_payment(fee, Decimal("1000.00"), "cash")
    assert payment.amount == Decimal("1000.00")
    assert payment.receipt_no.startswith("RCPT-")

    db.session.refresh(fee)
    assert fee.amount_paid == Decimal("1000.00")
    assert fee.status == FEE_PARTIAL
    assert fee.balance == Decimal("6700.00")


def test_full_payment_marks_fee_paid(fee):
    payment_service.record_payment(fee, fee.balance, "upi")
    db.session.refresh(fee)
    assert fee.status == FEE_PAID
    assert fee.balance == Decimal("0.00")


def test_overpayment_rejected(fee):
    with pytest.raises(OverpaymentError):
        payment_service.record_payment(fee, Decimal("999999.00"), "cash")
    db.session.refresh(fee)
    assert fee.amount_paid == Decimal("0.00")


def test_zero_payment_rejected(fee):
    with pytest.raises(PaymentError):
        payment_service.record_payment(fee, Decimal("0"), "cash")


def test_unsupported_method_rejected(fee):
    with pytest.raises(PaymentError):
        payment_service.record_payment(fee, Decimal("100.00"), "bitcoin")


def test_idempotency_key_prevents_duplicate(fee):
    first = payment_service.record_payment(
        fee, Decimal("500.00"), "cash", idempotency_key="dup-key"
    )
    second = payment_service.record_payment(
        fee, Decimal("500.00"), "cash", idempotency_key="dup-key"
    )
    assert first.id == second.id
    db.session.refresh(fee)
    assert fee.amount_paid == Decimal("500.00")


def test_reverse_payment_restores_balance(fee):
    payment = payment_service.record_payment(fee, Decimal("1000.00"), "cash")
    db.session.refresh(fee)
    assert fee.amount_paid == Decimal("1000.00")

    reversal = payment_service.reverse_payment(payment, "duplicate entry")
    assert reversal.reason == "duplicate entry"

    db.session.refresh(fee)
    assert fee.amount_paid == Decimal("0.00")
    db.session.refresh(payment)
    assert payment.status == "reversed"


def test_double_reversal_rejected(fee):
    payment = payment_service.record_payment(fee, Decimal("1000.00"), "cash")
    payment_service.reverse_payment(payment, "first")
    with pytest.raises(PaymentError):
        payment_service.reverse_payment(payment, "second")


def test_reversal_requires_reason(fee):
    payment = payment_service.record_payment(fee, Decimal("1000.00"), "cash")
    with pytest.raises(PaymentError):
        payment_service.reverse_payment(payment, "   ")


def test_route_record_payment(admin_client, room, make_student, fee_structures):
    student = make_student()
    allocation_service.allocate_bed(student)
    generated = fee_service.generate_fee(student, "2099-06")

    resp = admin_client.post(
        "/payments/new",
        data={
            "fee_id": generated.id,
            "amount": "1500.00",
            "method": "cash",
            "idempotency_key": "route-key-1",
            "notes": "",
        },
    )
    assert resp.status_code == 302
    db.session.refresh(generated)
    assert generated.amount_paid == Decimal("1500.00")


def test_route_reverse_payment(admin_client, room, make_student, fee_structures):
    student = make_student()
    allocation_service.allocate_bed(student)
    generated = fee_service.generate_fee(student, "2099-07")
    payment = payment_service.record_payment(generated, Decimal("1000.00"), "cash")

    resp = admin_client.post(f"/payments/{payment.id}/reverse", data={"reason": "mistake"})
    assert resp.status_code == 302
    db.session.refresh(generated)
    assert generated.amount_paid == Decimal("0.00")
