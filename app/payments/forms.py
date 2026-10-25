"""Payment forms."""

from __future__ import annotations

from flask_wtf import FlaskForm
from sqlalchemy import select
from wtforms import (
    DecimalField,
    HiddenField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.constants import PAYMENT_METHOD_LABELS, PAYMENT_METHODS
from app.extensions import db
from app.models import Student, StudentFee


def _outstanding_fees():
    return (
        db.session.execute(
            select(StudentFee)
            .join(Student, Student.id == StudentFee.student_id)
            .where(StudentFee.amount_paid < StudentFee.total_amount)
            .order_by(StudentFee.billing_period.desc())
        )
        .scalars()
        .all()
    )


class RecordPaymentForm(FlaskForm):
    fee_id = SelectField("Fee record", coerce=int, validators=[DataRequired()])
    amount = DecimalField("Amount", places=2, validators=[DataRequired(), NumberRange(min=0.01)])
    method = SelectField(
        "Method",
        choices=[(m, PAYMENT_METHOD_LABELS[m]) for m in PAYMENT_METHODS],
        validators=[DataRequired()],
    )
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=500)])
    idempotency_key = HiddenField()
    submit = SubmitField("Record payment")

    def __init__(self, *args, fixed_fee: StudentFee | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        if fixed_fee is not None:
            self.fee_id.choices = [
                (
                    fixed_fee.id,
                    f"{fixed_fee.student.roll_number} — {fixed_fee.period_label} "
                    f"(balance {fixed_fee.balance})",
                )
            ]
            if not self.fee_id.data:
                self.fee_id.data = fixed_fee.id
        else:
            self.fee_id.choices = [
                (
                    f.id,
                    f"{f.student.roll_number} — {f.period_label} (balance {f.balance})",
                )
                for f in _outstanding_fees()
            ]


class ReversePaymentForm(FlaskForm):
    reason = StringField("Reason for reversal", validators=[DataRequired(), Length(3, 255)])
    submit = SubmitField("Reverse payment")
