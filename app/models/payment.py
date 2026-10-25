"""Payment and payment-reversal models (immutable financial history)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.constants import PAYMENT_COMPLETED
from app.extensions import db
from app.models.base import ReprMixin, TimestampMixin


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Payment(TimestampMixin, ReprMixin, db.Model):
    """An immutable record of money received against a fee record."""

    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    fee_id = db.Column(
        db.Integer,
        db.ForeignKey("student_fees.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    method = db.Column(db.String(20), nullable=False, default="cash")
    reference = db.Column(db.String(40), unique=True, nullable=False, index=True)
    receipt_no = db.Column(db.String(40), unique=True, nullable=False, index=True)
    paid_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    recorded_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status = db.Column(db.String(20), nullable=False, default=PAYMENT_COMPLETED, index=True)
    # Guards against accidental double submission of the same form / request.
    idempotency_key = db.Column(db.String(80), unique=True, nullable=True)
    notes = db.Column(db.Text)

    fee = db.relationship("StudentFee", back_populates="payments", foreign_keys=[fee_id])
    student = db.relationship("Student", back_populates="payments", foreign_keys=[student_id])
    recorded_by = db.relationship("User", foreign_keys=[recorded_by_id])
    reversal = db.relationship(
        "PaymentReversal",
        back_populates="payment",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        db.CheckConstraint(
            "method IN ('cash', 'card', 'bank_transfer', 'upi', 'cheque')",
            name="ck_payments_method_valid",
        ),
        db.CheckConstraint("status IN ('completed', 'reversed')", name="ck_payments_status_valid"),
        db.Index("ix_payments_student_paid", "student_id", "paid_at"),
    )


class PaymentReversal(TimestampMixin, ReprMixin, db.Model):
    """A reversal/refund of a previously recorded payment.

    Payments are never edited or deleted; a correction is expressed as an
    additional reversal row that is linked one-to-one to its payment.
    """

    __tablename__ = "payment_reversals"

    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(
        db.Integer,
        db.ForeignKey("payments.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    reversed_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    payment = db.relationship("Payment", back_populates="reversal")
    reversed_by = db.relationship("User", foreign_keys=[reversed_by_id])

    __table_args__ = (db.CheckConstraint("amount > 0", name="ck_reversals_amount_positive"),)
