"""Student profile model."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.constants import (
    FEE_NONE,
    FEE_OVERDUE,
    FEE_PAID,
    FEE_PARTIAL,
    FEE_PENDING,
    STUDENT_ACTIVE,
)
from app.extensions import db
from app.models.base import ReprMixin, TimestampMixin


class Student(TimestampMixin, ReprMixin, db.Model):
    """A hostel resident and their profile information."""

    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
    )
    full_name = db.Column(db.String(150), nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=False)
    roll_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    course = db.Column(db.String(100), nullable=False, index=True)
    academic_year = db.Column(db.String(20), nullable=False, index=True)
    address = db.Column(db.Text)
    emergency_contact = db.Column(db.String(120))
    admission_date = db.Column(db.Date, nullable=False, default=date.today)
    status = db.Column(db.String(20), nullable=False, default=STUDENT_ACTIVE, index=True)

    user = db.relationship("User", back_populates="student", foreign_keys=[user_id])
    allocations = db.relationship(
        "RoomAllocation",
        back_populates="student",
        foreign_keys="RoomAllocation.student_id",
        order_by="desc(RoomAllocation.allocated_at)",
        cascade="save-update, merge",
    )
    active_allocations = db.relationship(
        "RoomAllocation",
        primaryjoin="and_(Student.id == RoomAllocation.student_id, "
        "RoomAllocation.status == 'active')",
        viewonly=True,
        order_by="RoomAllocation.bed_index",
        overlaps="allocations,student",
    )
    fees = db.relationship(
        "StudentFee",
        back_populates="student",
        foreign_keys="StudentFee.student_id",
        order_by="desc(StudentFee.billing_period)",
    )
    payments = db.relationship(
        "Payment",
        back_populates="student",
        foreign_keys="Payment.student_id",
        order_by="desc(Payment.paid_at)",
    )

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('active', 'inactive', 'archived')",
            name="ck_students_status_valid",
        ),
        db.Index("ix_students_status_course", "status", "course"),
        db.Index("ix_students_status_year", "status", "academic_year"),
    )

    # -- derived helpers ---------------------------------------------------
    @property
    def current_allocation(self):
        return self.active_allocations[0] if self.active_allocations else None

    @property
    def current_room(self):
        alloc = self.current_allocation
        return alloc.room if alloc else None

    @property
    def is_active(self) -> bool:
        return self.status == STUDENT_ACTIVE

    @property
    def outstanding_balance(self) -> Decimal:
        return sum((f.balance for f in self.fees), Decimal("0.00"))

    @property
    def total_billed(self) -> Decimal:
        return sum((f.total_amount for f in self.fees), Decimal("0.00"))

    @property
    def total_paid(self) -> Decimal:
        return sum((f.amount_paid for f in self.fees), Decimal("0.00"))

    @property
    def fee_status(self) -> str:

        fees = self.fees
        if not fees:
            return FEE_NONE
        today = date.today()
        balances = [f.balance for f in fees]
        total_balance = sum(balances, Decimal("0.00"))
        if total_balance <= 0:
            return FEE_PAID
        if any(f.balance > 0 and f.due_date and f.due_date < today for f in fees):
            return FEE_OVERDUE
        if any(Decimal("0.00") < f.amount_paid < f.total_amount for f in fees):
            return FEE_PARTIAL
        return FEE_PENDING
