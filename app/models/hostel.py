"""Hostel / building model."""

from __future__ import annotations

from app.extensions import db
from app.models.base import ReprMixin, TimestampMixin


class Hostel(TimestampMixin, ReprMixin, db.Model):
    """A physical hostel building that contains rooms."""

    __tablename__ = "hostels"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False, index=True)
    address = db.Column(db.String(255))
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    rooms = db.relationship(
        "Room",
        back_populates="hostel",
        order_by="Room.room_number",
        cascade="save-update, merge",
    )

    @property
    def total_capacity(self) -> int:
        return sum(r.capacity for r in self.rooms)

    @property
    def occupied_beds(self) -> int:
        return sum(r.occupied_beds for r in self.rooms)
