"""Student self-service portal routes."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from flask import abort, flash, redirect, render_template, url_for
from flask_login import current_user
from sqlalchemy import select

from app.extensions import db
from app.models import Payment, RoomAllocation, Student, StudentFee
from app.services import audit_service
from app.utils.decorators import flash_form_errors, student_required

from . import portal_bp
from .forms import StudentSelfEditForm


def current_student() -> Student:
    student = current_user.student
    if student is None:
        abort(403, "No student profile is linked to this account.")
    return student


@portal_bp.route("/")
@student_required
def dashboard():
    student = current_student()
    fees = (
        db.session.execute(
            select(StudentFee)
            .where(StudentFee.student_id == student.id)
            .order_by(StudentFee.billing_period.desc())
        )
        .scalars()
        .all()
    )
    payments = (
        db.session.execute(
            select(Payment)
            .where(Payment.student_id == student.id)
            .order_by(Payment.paid_at.desc())
            .limit(5)
        )
        .scalars()
        .all()
    )
    allocation = student.current_allocation
    upcoming = next((f for f in sorted(fees, key=lambda x: x.due_date) if f.balance > 0), None)
    total_billed = sum((f.total_amount for f in fees), Decimal("0.00"))
    total_paid = sum((f.amount_paid for f in fees), Decimal("0.00"))
    outstanding = sum((f.balance for f in fees), Decimal("0.00"))
    return render_template(
        "students/dashboard.html",
        student=student,
        fees=fees,
        payments=payments,
        allocation=allocation,
        upcoming=upcoming,
        total_billed=total_billed,
        total_paid=total_paid,
        outstanding=outstanding,
        today=date.today(),
    )


@portal_bp.route("/profile")
@student_required
def profile():
    student = current_student()
    return render_template("students/profile.html", student=student)


@portal_bp.route("/profile/edit", methods=["GET", "POST"])
@student_required
def edit_profile():
    student = current_student()
    form = StudentSelfEditForm(obj=student)
    if form.validate_on_submit():
        student.phone = form.phone.data.strip()
        student.address = form.address.data
        student.emergency_contact = form.emergency_contact.data
        audit_service.log_action("student.self_update", "student", student.id)
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("portal.profile"))
    elif form.is_submitted():
        flash_form_errors(form)
    return render_template("students/profile_edit.html", form=form, student=student)


@portal_bp.route("/allocations")
@student_required
def allocations():
    student = current_student()
    history = (
        db.session.execute(
            select(RoomAllocation)
            .where(RoomAllocation.student_id == student.id)
            .order_by(RoomAllocation.allocated_at.desc())
        )
        .scalars()
        .all()
    )
    return render_template(
        "students/allocations.html",
        student=student,
        history=history,
        current=student.current_allocation,
    )


@portal_bp.route("/fees")
@student_required
def fees():
    student = current_student()
    records = (
        db.session.execute(
            select(StudentFee)
            .where(StudentFee.student_id == student.id)
            .order_by(StudentFee.billing_period.desc())
        )
        .scalars()
        .all()
    )
    return render_template("students/fees.html", student=student, records=records)


@portal_bp.route("/fees/<int:fee_id>")
@student_required
def fee_detail(fee_id):
    student = current_student()
    fee = db.session.get(StudentFee, fee_id)
    if fee is None or fee.student_id != student.id:
        abort(404)
    return render_template("students/fee_detail.html", student=student, fee=fee)


@portal_bp.route("/payments")
@student_required
def payments():
    student = current_student()
    records = (
        db.session.execute(
            select(Payment).where(Payment.student_id == student.id).order_by(Payment.paid_at.desc())
        )
        .scalars()
        .all()
    )
    return render_template("students/payments.html", student=student, payments=records)


@portal_bp.route("/receipts/<int:payment_id>")
@student_required
def receipt(payment_id):
    from app.payments.routes import send_receipt

    student = current_student()
    payment = db.session.get(Payment, payment_id)
    if payment is None or payment.student_id != student.id:
        abort(404)
    return send_receipt(payment)
