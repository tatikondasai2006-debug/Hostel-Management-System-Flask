"""Payment recording service.

Payments are immutable: a correction is never an ``UPDATE``/``DELETE`` but a
linked :class:`PaymentReversal`.  Balances are updated inside a transaction
that locks the parent fee row (``SELECT ... FOR UPDATE``) so concurrent
payments against the same bill cannot overpay it.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.constants import PAYMENT_COMPLETED, PAYMENT_METHODS, PAYMENT_REVERSED
from app.extensions import db
from app.models import Payment, PaymentReversal, StudentFee
from app.services import fee_service
from app.utils.money import money, to_decimal

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5


class PaymentError(Exception):
    """Raised when a payment cannot be recorded."""


class OverpaymentError(PaymentError):
    """Raised when an amount exceeds the outstanding balance."""


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_reference(prefix: str) -> str:
    return f"{prefix}-{datetime.now(UTC):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


def _lock_fee(fee_id: int) -> StudentFee:
    fee = db.session.execute(
        select(StudentFee).where(StudentFee.id == fee_id).with_for_update()
    ).scalar_one_or_none()
    if fee is None:
        raise PaymentError("Fee record no longer exists.")
    return fee


def recompute_paid_from_payments(fee: StudentFee) -> Decimal:
    """Derive ``amount_paid`` from completed payments (integrity helper)."""
    total = db.session.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.fee_id == fee.id,
            Payment.status == PAYMENT_COMPLETED,
        )
    ).scalar_one() or Decimal("0.00")
    fee.amount_paid = money(total)
    fee_service.recompute_totals(fee)
    return fee.amount_paid


def record_payment(
    fee: StudentFee,
    amount,
    method: str,
    recorded_by=None,
    notes: str | None = None,
    idempotency_key: str | None = None,
    paid_at: datetime | None = None,
    commit: bool = True,
) -> Payment:
    """Record a payment against ``fee`` and update balances transactionally."""
    amount = money(amount)
    if amount <= 0:
        raise PaymentError("Payment amount must be greater than zero.")
    if method not in PAYMENT_METHODS:
        raise PaymentError("Unsupported payment method.")

    # Idempotency: an identical submission must not be processed twice.
    if idempotency_key:
        existing = db.session.execute(
            select(Payment).where(Payment.idempotency_key == idempotency_key)
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    last_exc: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            locked = _lock_fee(fee.id)
            fee_service.recompute_totals(locked)
            balance = locked.balance
            if amount > balance:
                db.session.rollback()
                raise OverpaymentError(
                    f"Amount {amount} exceeds the outstanding balance {balance}."
                )
            payment = Payment(
                fee_id=locked.id,
                student_id=locked.student_id,
                amount=amount,
                method=method,
                reference=_new_reference("PAY"),
                receipt_no=_new_reference("RCPT"),
                paid_at=paid_at or _utcnow(),
                recorded_by_id=getattr(recorded_by, "id", None),
                status=PAYMENT_COMPLETED,
                idempotency_key=idempotency_key,
                notes=notes,
            )
            locked.amount_paid = money(to_decimal(locked.amount_paid) + amount)
            fee_service.refresh_status(locked)
            db.session.add(payment)
            db.session.flush()
            if commit:
                db.session.commit()
            return payment
        except OverpaymentError:
            raise
        except IntegrityError as exc:
            db.session.rollback()
            last_exc = exc
            # Reference collision or a concurrent idempotent insert: retry.
            if idempotency_key:
                existing = db.session.execute(
                    select(Payment).where(Payment.idempotency_key == idempotency_key)
                ).scalar_one_or_none()
                if existing is not None:
                    return existing
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(0.05 * (2**attempt))
    raise PaymentError(
        "Could not record the payment due to a concurrent update. Please retry."
    ) from last_exc


def reverse_payment(
    payment: Payment, reason: str, reversed_by=None, commit: bool = True
) -> PaymentReversal:
    """Reverse a payment, restoring the fee balance."""
    locked = db.session.execute(
        select(Payment).where(Payment.id == payment.id).with_for_update()
    ).scalar_one_or_none()
    if locked is None:
        raise PaymentError("Payment no longer exists.")
    if locked.status == PAYMENT_REVERSED:
        raise PaymentError("This payment has already been reversed.")
    if not reason or not reason.strip():
        raise PaymentError("A reason is required to reverse a payment.")

    fee = _lock_fee(locked.fee_id)
    reversal = PaymentReversal(
        payment_id=locked.id,
        amount=money(locked.amount),
        reason=reason.strip()[:255],
        reversed_by_id=getattr(reversed_by, "id", None),
    )
    locked.status = PAYMENT_REVERSED
    new_paid = money(to_decimal(fee.amount_paid) - to_decimal(locked.amount))
    fee.amount_paid = new_paid if new_paid > 0 else Decimal("0.00")
    fee_service.refresh_status(fee)
    db.session.add(reversal)
    if commit:
        db.session.commit()
    return reversal


def student_outstanding(student_id: int) -> Decimal:
    value = db.session.execute(
        select(func.coalesce(func.sum(StudentFee.total_amount - StudentFee.amount_paid), 0)).where(
            StudentFee.student_id == student_id
        )
    ).scalar_one()
    return money(value or 0)
