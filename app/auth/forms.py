"""Authentication forms."""

from __future__ import annotations

import re

from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    Regexp,
    ValidationError,
)

PASSWORD_RULE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).+$")


def validate_password_strength(form, field):
    value = field.data or ""
    if len(value) < 8:
        raise ValidationError("Password must be at least 8 characters long.")
    if not PASSWORD_RULE.match(value):
        raise ValidationError("Password must contain at least one letter and one number.")


class LoginForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[DataRequired(), Email(message="Enter a valid email address."), Length(max=255)],
    )
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember me")
    submit = SubmitField("Sign in")


class SignupForm(FlaskForm):
    full_name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=150)])
    email = StringField(
        "Email",
        validators=[DataRequired(), Email(), Length(max=255)],
    )
    phone = StringField(
        "Phone number",
        validators=[
            DataRequired(),
            Regexp(r"^[0-9+\-\s()]{7,30}$", message="Enter a valid phone number."),
        ],
    )
    roll_number = StringField("Roll number", validators=[DataRequired(), Length(min=2, max=50)])
    course = StringField("Course", validators=[DataRequired(), Length(max=100)])
    academic_year = StringField("Academic year", validators=[DataRequired(), Length(max=20)])
    address = StringField("Address", validators=[Length(max=500)])
    emergency_contact = StringField("Emergency contact", validators=[Length(max=120)])
    password = PasswordField("Password", validators=[DataRequired(), validate_password_strength])
    confirm_password = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Create account")
