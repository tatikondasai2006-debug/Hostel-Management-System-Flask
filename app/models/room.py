"""Room model."""

from __future__ import annotations

from app.constants import (
    ROOM_AVAILABLE,
    ROOM_FULL,
    ROOM_PARTIAL,
)
from app.extensions import db
from app.models.base import ReprMixin, TimestampMixin


class Room(TimestampMixin, ReprMixin, db.Model):
    """A bookable room with a fixed bed capacity."""

    __tablename__ = "rooms"

    id = db.Column(db.Integer, primary_key=True)
    hostel_id = db.Column(
        db.Integer,
        db.ForeignKey("hostels.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    room_number = db.Column(db.String(20), nullable=False, index=True)
    floor = db.Column(db.Integer, nullable=False, default=0)
    room_type = db.Column(db.String(20), nullable=False, default="single", index=True)
    capacity = db.Column(db.Integer, nullable=False, default=1)
    base_fee = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default=ROOM_AVAILABLE, index=True)
    amenities = db.Column(db.Text)

    hostel = db.relationship("Hostel", back_populates="rooms")
    allocations = db.relationship(
        "RoomAllocation",
        back_populates="room",
        foreign_keys="RoomAllocation.room_id",
        order_by="RoomAllocation.bed_index",
    )
    active_allocations = db.relationship(
        "RoomAllocation",
        primaryjoin="and_(Room.id == RoomAllocation.room_id, RoomAllocation.status == 'active')",
        viewonly=True,
        order_by="RoomAllocation.bed_index",
        overlaps="allocations,room",
    )

    __table_args__ = (
        db.UniqueConstraint("hostel_id", "room_number", name="uq_room_number_per_hostel"),
        db.CheckConstraint("capacity > 0", name="ck_rooms_capacity_positive"),
        db.CheckConstraint("capacity <= 50", name="ck_rooms_capacity_max"),
        db.CheckConstraint("base_fee >= 0", name="ck_rooms_base_fee_non_negative"),
        db.CheckConstraint(
            "room_type IN ('single', 'double', 'dormitory')",
            name="ck_rooms_type_valid",
        ),
        db.CheckConstraint(
            "status IN ('available', 'maintenance', 'unavailable')",
            name="ck_rooms_status_valid",
        ),
        db.Index("ix_rooms_status_type", "status", "room_type"),
    )

    # -- derived helpers ---------------------------------------------------
    @property
    def occupied_beds(self) -> int:
        return len(self.active_allocations)

    @property
    def available_beds(self) -> int:
        return max(self.capacity - self.occupied_beds, 0)

    @property
    def is_full(self) -> bool:
        return self.occupied_beds >= self.capacity

    @property
    def occupancy_percent(self) -> float:
        if self.capacity <= 0:
            return 0.0
        return round(self.occupied_beds / self.capacity * 100, 1)

    @property
    def display_status(self) -> str:
        """Human-facing status combining lifecycle status + occupancy."""
        if self.status != ROOM_AVAILABLE:
            return self.status
        if self.is_full:
            return ROOM_FULL
        if self.occupied_beds > 0:
            return ROOM_PARTIAL
        return ROOM_AVAILABLE

    @property
    def active_students(self):
        return [a.student for a in self.active_allocations if a.student]
