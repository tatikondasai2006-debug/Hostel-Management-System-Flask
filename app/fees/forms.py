"""Fee forms."""

from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    DecimalField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    Length,
    NumberRange,
    Optional,
    Regexp,
    ValidationError,
)


class GenerateFeesForm(FlaskForm):
    billing_period = StringField(
        "Billing period (YYYY-MM)",
        validators=[
            DataRequired(),
            Regexp(r"^\d{4}-(0[1-9]|1[0-2])$", message="Use the format YYYY-MM."),
        ],
    )
    due_date = DateField("Due date (optional)", validators=[Optional()])
    scope = SelectField(
        "Generate for",
        choices=[
            ("active", "All active students"),
            ("allocated", "Only students with a room"),
        ],
        validators=[DataRequired()],
    )
    other_amount = DecimalField(
        "Additional charge", places=2, default=0, validators=[NumberRange(min=0)]
    )
    submit = SubmitField("Generate bills")


class FeeAdjustForm(FlaskForm):
    other_amount = DecimalField(
        "Other charges", places=2, validators=[DataRequired(), NumberRange(min=0)]
    )
    discount_amount = DecimalField(
        "Discount / concession", places=2, validators=[DataRequired(), NumberRange(min=0)]
    )
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Update bill")

    def validate_discount_amount(self, field):
        if field.data is not None and field.data < 0:
            raise ValidationError("Discount cannot be negative.")


class FeeStructureForm(FlaskForm):
    monthly_amount = DecimalField(
        "Monthly accommodation", places=2, validators=[DataRequired(), NumberRange(min=0)]
    )
    mess_amount = DecimalField(
        "Mess charge", places=2, validators=[DataRequired(), NumberRange(min=0)]
    )
    laundry_amount = DecimalField(
        "Laundry charge", places=2, validators=[DataRequired(), NumberRange(min=0)]
    )
    maintenance_amount = DecimalField(
        "Maintenance charge", places=2, validators=[DataRequired(), NumberRange(min=0)]
    )
    description = StringField("Description", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Save fee structure")
