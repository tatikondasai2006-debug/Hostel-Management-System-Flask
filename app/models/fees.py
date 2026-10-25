"""Fee structures and per-student billing records."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.constants import FEE_PENDING
from app.extensions import db
from app.models.base import ReprMixin, TimestampMixin


class FeeStructure(TimestampMixin, ReprMixin, db.Model):
    """Configurable default pricing per room type.

    The accommodation amount defaults to this rate, but a room may carry its
    own ``base_fee`` override (e.g. premium rooms).
    """

    __tablename__ = "fee_structures"

    id = db.Column(db.Integer, primary_key=True)
    room_type = db.Column(db.String(20), unique=True, nullable=False)
    monthly_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    mess_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    laundry_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    maintenance_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    description = db.Column(db.String(255))

    __table_args__ = (
        db.CheckConstraint(
            "room_type IN ('single', 'double', 'dormitory')",
            name="ck_fee_structures_type_valid",
        ),
        db.CheckConstraint("monthly_amount >= 0", name="ck_fee_structures_monthly_non_negative"),
        db.CheckConstraint("mess_amount >= 0", name="ck_fee_structures_mess_non_negative"),
        db.CheckConstraint("laundry_amount >= 0", name="ck_fee_structures_laundry_non_negative"),
        db.CheckConstraint("maintenance_amount >= 0", name="ck_fee_structures_maint_non_negative"),
    )


class StudentFee(TimestampMixin, ReprMixin, db.Model):
    """A monthly bill for a single student and billing period."""

    __tablename__ = "student_fees"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    fee_structure_id = db.Column(
        db.Integer, db.ForeignKey("fee_structures.id", ondelete="SET NULL")
    )
    room_id = db.Column(db.Integer, db.ForeignKey("rooms.id", ondelete="SET NULL"))
    billing_period = db.Column(db.String(7), nullable=False, index=True)
    room_type = db.Column(db.String(20))
    accommodation_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    mess_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    laundry_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    maintenance_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    other_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    discount_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    late_fee_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    amount_paid = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=FEE_PENDING, index=True)
    notes = db.Column(db.Text)

    student = db.relationship("Student", back_populates="fees", foreign_keys=[student_id])
    fee_structure = db.relationship("FeeStructure")
    room = db.relationship("Room")
    payments = db.relationship(
        "Payment",
        back_populates="fee",
        foreign_keys="Payment.fee_id",
        order_by="Payment.paid_at",
    )

    __table_args__ = (
        db.UniqueConstraint("student_id", "billing_period", name="uq_fee_period_per_student"),
        db.CheckConstraint("billing_period LIKE '____-__'", name="ck_fee_period_format"),
        db.CheckConstraint("total_amount >= 0", name="ck_fees_total_non_negative"),
        db.CheckConstraint("amount_paid >= 0", name="ck_fees_paid_non_negative"),
        db.CheckConstraint("amount_paid <= total_amount", name="ck_fees_paid_not_over_total"),
        db.CheckConstraint(
            "status IN ('pending', 'partial', 'paid', 'overdue')",
            name="ck_fees_status_valid",
        ),
        db.CheckConstraint("discount_amount >= 0", name="ck_fees_discount_non_negative"),
        db.CheckConstraint("late_fee_amount >= 0", name="ck_fees_late_fee_non_negative"),
        db.Index("ix_fees_student_status", "student_id", "status"),
    )

    # -- derived helpers ---------------------------------------------------
    @property
    def balance(self) -> Decimal:
        return (self.total_amount or Decimal("0.00")) - (self.amount_paid or Decimal("0.00"))

    @property
    def is_paid(self) -> bool:
        return self.balance <= 0

    @property
    def is_overdue(self) -> bool:
        return bool(self.balance > 0 and self.due_date and self.due_date < date.today())

    @property
    def period_label(self) -> str:
        """'2026-04' -> 'April 2026'."""
        try:
            year, month = self.billing_period.split("-")
            return date(int(year), int(month), 1).strftime("%B %Y")
        except (ValueError, AttributeError):
            return self.billing_period or ""
