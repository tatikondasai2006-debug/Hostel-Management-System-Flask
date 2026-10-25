"""Room and hostel forms."""

from __future__ import annotations

from flask_wtf import FlaskForm
from sqlalchemy import select
from wtforms import (
    DecimalField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError

from app.constants import (
    ROOM_STATUSES,
    ROOM_TYPE_LABELS,
    ROOM_TYPES,
)
from app.extensions import db
from app.models import Hostel, Room


class HostelForm(FlaskForm):
    name = StringField("Hostel name", validators=[DataRequired(), Length(2, 120)])
    address = StringField("Address", validators=[Optional(), Length(max=255)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=1000)])
    submit = SubmitField("Save hostel")

    def __init__(self, *args, hostel: Hostel | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.hostel = hostel

    def validate_name(self, field):
        stmt = select(Hostel).where(Hostel.name == field.data.strip())
        if self.hostel is not None:
            stmt = stmt.where(Hostel.id != self.hostel.id)
        if db.session.execute(stmt).scalar_one_or_none():
            raise ValidationError("A hostel with that name already exists.")


class RoomForm(FlaskForm):
    hostel_id = SelectField("Hostel", coerce=int, validators=[DataRequired()])
    room_number = StringField("Room number", validators=[DataRequired(), Length(1, 20)])
    floor = IntegerField("Floor", validators=[DataRequired(), NumberRange(min=-5, max=100)])
    room_type = SelectField(
        "Room type",
        choices=[(t, ROOM_TYPE_LABELS[t]) for t in ROOM_TYPES],
        validators=[DataRequired()],
    )
    capacity = IntegerField("Capacity", validators=[DataRequired(), NumberRange(min=1, max=50)])
    base_fee = DecimalField(
        "Monthly base fee",
        places=2,
        validators=[DataRequired(), NumberRange(min=0)],
    )
    status = SelectField(
        "Status",
        choices=[(s, s.title()) for s in ROOM_STATUSES],
        validators=[DataRequired()],
    )
    amenities = TextAreaField("Amenities", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Save room")

    def __init__(self, *args, room: Room | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.room = room
        try:
            self.hostel_id.choices = [
                (h.id, h.name)
                for h in db.session.execute(select(Hostel).order_by(Hostel.name)).scalars()
            ]
        except Exception:  # pragma: no cover - outside app context
            self.hostel_id.choices = []

    def validate_capacity(self, field):
        if self.room is not None and field.data < self.room.occupied_beds:
            raise ValidationError(
                f"Capacity cannot be lower than current occupancy ({self.room.occupied_beds})."
            )

    def validate_room_number(self, field):
        stmt = select(Room).where(
            Room.hostel_id == self.hostel_id.data,
            Room.room_number == field.data.strip(),
        )
        if self.room is not None:
            stmt = stmt.where(Room.id != self.room.id)
        if db.session.execute(stmt).scalar_one_or_none():
            raise ValidationError("That room number already exists in this hostel.")
