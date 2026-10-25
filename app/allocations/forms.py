"""Allocation forms."""

from __future__ import annotations

from flask_wtf import FlaskForm
from sqlalchemy import select
from wtforms import SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Optional

from app.constants import ALLOCATION_ACTIVE, ROOM_AVAILABLE, STUDENT_ACTIVE
from app.extensions import db
from app.models import Room, RoomAllocation, Student


def _unallocated_students():
    allocated = select(RoomAllocation.student_id).where(RoomAllocation.status == ALLOCATION_ACTIVE)
    return (
        db.session.execute(
            select(Student)
            .where(Student.status == STUDENT_ACTIVE, Student.id.notin_(allocated))
            .order_by(Student.roll_number)
        )
        .scalars()
        .all()
    )


def _rooms_with_space():
    rooms = (
        db.session.execute(
            select(Room).where(Room.status == ROOM_AVAILABLE).order_by(Room.room_number)
        )
        .scalars()
        .all()
    )
    return [r for r in rooms if not r.is_full]


class AutoAllocateForm(FlaskForm):
    student_id = SelectField("Student", coerce=int, validators=[DataRequired()])
    room_type = SelectField(
        "Preferred room type",
        choices=[
            ("", "Any"),
            ("single", "Single"),
            ("double", "Double"),
            ("dormitory", "Dormitory"),
        ],
    )
    notes = StringField("Notes", validators=[Optional()])
    submit = SubmitField("Allocate automatically")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.student_id.choices = [
            (s.id, f"{s.roll_number} — {s.full_name}") for s in _unallocated_students()
        ]


class ManualAssignForm(FlaskForm):
    student_id = SelectField("Student", coerce=int, validators=[DataRequired()])
    room_id = SelectField("Room (available bed)", coerce=int, validators=[DataRequired()])
    notes = StringField("Notes", validators=[Optional()])
    submit = SubmitField("Assign room")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.student_id.choices = [
            (s.id, f"{s.roll_number} — {s.full_name}") for s in _unallocated_students()
        ]
        self.room_id.choices = [
            (
                r.id,
                f"{r.hostel.name} / {r.room_number} ({r.room_type}, {r.available_beds} free)",
            )
            for r in _rooms_with_space()
        ]


class TransferForm(FlaskForm):
    room_id = SelectField("New room", coerce=int, validators=[DataRequired()])
    notes = StringField("Notes", validators=[Optional()])
    submit = SubmitField("Transfer student")

    def __init__(self, *args, exclude_room_id: int | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.room_id.choices = [
            (
                r.id,
                f"{r.hostel.name} / {r.room_number} ({r.room_type}, {r.available_beds} free)",
            )
            for r in _rooms_with_space()
            if r.id != exclude_room_id
        ]


class ReleaseForm(FlaskForm):
    reason = StringField("Reason", validators=[Optional()])
    submit = SubmitField("Release bed")
