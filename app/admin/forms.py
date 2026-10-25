"""Administrator settings form."""

from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import DecimalField, IntegerField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional


class SettingsForm(FlaskForm):
    hostel_name = StringField("Hostel name", validators=[DataRequired(), Length(2, 120)])
    hostel_address = StringField("Address", validators=[Optional(), Length(max=255)])
    hostel_contact = StringField("Contact phone", validators=[Optional(), Length(max=60)])
    hostel_email = StringField("Contact email", validators=[Optional(), Email(), Length(max=255)])
    currency_symbol = StringField("Currency symbol", validators=[DataRequired(), Length(1, 5)])
    late_fee_percent = DecimalField(
        "Late fee (% of outstanding)",
        places=2,
        validators=[DataRequired(), NumberRange(min=0, max=100)],
    )
    late_fee_grace_days = IntegerField(
        "Grace period (days)", validators=[DataRequired(), NumberRange(min=0, max=90)]
    )
    submit = SubmitField("Save settings")
