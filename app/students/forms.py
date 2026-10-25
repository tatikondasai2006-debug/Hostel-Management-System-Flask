"""Student forms."""

from __future__ import annotations

import re

from flask_wtf import FlaskForm
from sqlalchemy import select
from wtforms import (
    BooleanField,
    DateField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    Optional,
    Regexp,
    ValidationError,
)

from app.constants import STUDENT_STATUSES
from app.extensions import db
from app.models import Student, User


def _strong_password(form, field):
    value = field.data or ""
    if not value:
        return
    if len(value) < 8 or not re.match(r"^(?=.*[A-Za-z])(?=.*\d).+$", value):
        raise ValidationError("Password must be 8+ chars with letters and numbers.")


class StudentForm(FlaskForm):
    full_name = StringField("Full name", validators=[DataRequired(), Length(2, 150)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    phone = StringField(
        "Phone",
        validators=[
            DataRequired(),
            Regexp(r"^[0-9+\-\s()]{7,30}$", message="Invalid phone number."),
        ],
    )
    roll_number = StringField("Roll number", validators=[DataRequired(), Length(2, 50)])
    course = StringField("Course", validators=[DataRequired(), Length(max=100)])
    academic_year = StringField("Academic year", validators=[DataRequired(), Length(max=20)])
    address = TextAreaField("Address", validators=[Optional(), Length(max=500)])
    emergency_contact = StringField("Emergency contact", validators=[Optional(), Length(max=120)])
    admission_date = DateField("Admission date", validators=[DataRequired()])
    status = SelectField(
        "Status",
        choices=[(s, s.title()) for s in STUDENT_STATUSES],
        validators=[DataRequired()],
    )
    create_login = BooleanField("Create / update portal login")
    password = PasswordField(
        "Portal password (optional)", validators=[Optional(), _strong_password]
    )
    submit = SubmitField("Save student")

    def __init__(self, *args, student: Student | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.student = student

    def validate_email(self, field):
        email = field.data.strip().lower()
        stmt = select(Student).where(Student.email == email)
        if self.student is not None:
            stmt = stmt.where(Student.id != self.student.id)
        if db.session.execute(stmt).scalar_one_or_none():
            raise ValidationError("Another student already uses that email.")
        if (
            self.student is None
            and db.session.execute(select(User).where(User.email == email)).scalar_one_or_none()
        ):
            raise ValidationError("A user account already uses that email.")

    def validate_roll_number(self, field):
        roll = field.data.strip()
        stmt = select(Student).where(Student.roll_number == roll)
        if self.student is not None:
            stmt = stmt.where(Student.id != self.student.id)
        if db.session.execute(stmt).scalar_one_or_none():
            raise ValidationError("Another student already uses that roll number.")


class StudentSelfEditForm(FlaskForm):
    """Fields a student is allowed to update themselves."""

    phone = StringField(
        "Phone",
        validators=[
            DataRequired(),
            Regexp(r"^[0-9+\-\s()]{7,30}$", message="Invalid phone number."),
        ],
    )
    address = TextAreaField("Address", validators=[Optional(), Length(max=500)])
    emergency_contact = StringField("Emergency contact", validators=[Optional(), Length(max=120)])
    submit = SubmitField("Update profile")
