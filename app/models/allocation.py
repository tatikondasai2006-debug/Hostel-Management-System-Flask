"""Room allocation model (current assignments + history)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.constants import ALLOCATION_ACTIVE
from app.extensions import db
from app.models.base import ReprMixin, TimestampMixin


def _utcnow() -> datetime:
    return datetime.now(UTC)


class RoomAllocation(TimestampMixin, ReprMixin, db.Model):
    """A bed reservation for a student.

    Active rows (``status == 'active'``) represent current occupancy; released
    rows are the immutable allocation history.  Two PostgreSQL partial unique
    indexes guarantee at the database level that a student has at most one
    active allocation and that a bed is never double-booked.
    """

    __tablename__ = "room_allocations"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    room_id = db.Column(
        db.Integer,
        db.ForeignKey("rooms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    bed_index = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=ALLOCATION_ACTIVE, index=True)
    allocated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    released_at = db.Column(db.DateTime(timezone=True), nullable=True)
    allocated_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    release_reason = db.Column(db.String(30), nullable=True)
    notes = db.Column(db.Text)

    student = db.relationship("Student", back_populates="allocations", foreign_keys=[student_id])
    room = db.relationship("Room", back_populates="allocations", foreign_keys=[room_id])
    allocated_by = db.relationship("User", foreign_keys=[allocated_by_id])

    __table_args__ = (
        db.CheckConstraint("status IN ('active', 'released')", name="ck_allocations_status_valid"),
        db.CheckConstraint("bed_index >= 1", name="ck_allocations_bed_index_positive"),
        db.CheckConstraint(
            "released_at IS NULL OR released_at >= allocated_at",
            name="ck_allocations_release_after_alloc",
        ),
        # one active allocation per student
        db.Index(
            "uq_active_allocation_per_student",
            "student_id",
            unique=True,
            postgresql_where=db.text("status = 'active'"),
            sqlite_where=db.text("status = 'active'"),
        ),
        # a bed can only be occupied once
        db.Index(
            "uq_active_allocation_per_bed",
            "room_id",
            "bed_index",
            unique=True,
            postgresql_where=db.text("status = 'active'"),
            sqlite_where=db.text("status = 'active'"),
        ),
        db.Index("ix_allocations_status_room", "status", "room_id"),
    )

    @property
    def is_active(self) -> bool:
        return self.status == ALLOCATION_ACTIVE
