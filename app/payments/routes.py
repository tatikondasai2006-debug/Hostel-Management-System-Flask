"""Payment processing + PDF receipt routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time
from decimal import Decimal

from flask import (
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user
from sqlalchemy import or_, select

from app.constants import PAYMENT_METHODS
from app.extensions import db
from app.models import Payment, Student, StudentFee
from app.services import audit_service, payment_service, receipt_service
from app.utils.decorators import admin_required, flash_form_errors
from app.utils.pagination import page_args, query_string_without_page

from . import payments_bp
from .forms import RecordPaymentForm, ReversePaymentForm


def send_receipt(payment: Payment) -> Response:
    """Build the PDF receipt HTTP response for ``payment``."""
    pdf_bytes = receipt_service.build_receipt_pdf(payment)
    response = Response(pdf_bytes, mimetype="application/pdf")
    filename = f"receipt-{payment.receipt_no}.pdf"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@payments_bp.route("/")
@admin_required
def list_payments():
    page, per_page = page_args(20)
    stmt = select(Payment).join(Student, Student.id == Payment.student_id)

    search = (request.args.get("q") or "").strip()
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                Student.full_name.ilike(like),
                Student.roll_number.ilike(like),
                Payment.reference.ilike(like),
                Payment.receipt_no.ilike(like),
            )
        )
    if request.args.get("method") in PAYMENT_METHODS:
        stmt = stmt.where(Payment.method == request.args["method"])
    start_date = _parse_date(request.args.get("start_date"))
    end_date = _parse_date(request.args.get("end_date"))
    if start_date:
        stmt = stmt.where(Payment.paid_at >= datetime.combine(start_date, time.min, tzinfo=UTC))
    if end_date:
        stmt = stmt.where(Payment.paid_at <= datetime.combine(end_date, time.max, tzinfo=UTC))

    stmt = stmt.order_by(Payment.paid_at.desc())
    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)
    total = sum((p.amount for p in pagination.items), Decimal("0.00"))
    return render_template(
        "payments/list.html",
        pagination=pagination,
        payments=pagination.items,
        methods=PAYMENT_METHODS,
        filters=request.args,
        query_string=query_string_without_page(),
        page_total=total,
    )


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@payments_bp.route("/new", methods=["GET", "POST"])
@admin_required
def record_payment():
    fee_id = request.args.get("fee_id", type=int)
    fixed_fee = db.session.get(StudentFee, fee_id) if fee_id else None
    form = RecordPaymentForm(fixed_fee=fixed_fee)
    if request.method == "GET" and fixed_fee is not None:
        form.amount.data = fixed_fee.balance
        form.idempotency_key.data = uuid.uuid4().hex
    if form.validate_on_submit():
        fee = db.session.get(StudentFee, form.fee_id.data) or abort(404)
        key = form.idempotency_key.data or uuid.uuid4().hex
        try:
            payment = payment_service.record_payment(
                fee,
                form.amount.data,
                form.method.data,
                recorded_by=current_user,
                notes=form.notes.data,
                idempotency_key=key,
            )
        except payment_service.PaymentError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        else:
            audit_service.log_action(
                "payment.record",
                "payment",
                payment.id,
                {"fee": fee.id, "amount": str(payment.amount)},
            )
            db.session.commit()
            flash(
                f"Payment of {payment.amount} recorded. Receipt {payment.receipt_no}.",
                "success",
            )
            return redirect(url_for("payments.list_payments"))
    elif form.is_submitted():
        flash_form_errors(form)
    return render_template("payments/record.html", form=form, fee=fixed_fee)


@payments_bp.route("/<int:payment_id>")
@admin_required
def view_payment(payment_id):
    payment = db.session.get(Payment, payment_id) or abort(404)
    return render_template(
        "payments/detail.html", payment=payment, reverse_form=ReversePaymentForm()
    )


@payments_bp.route("/<int:payment_id>/receipt")
@admin_required
def receipt(payment_id):
    payment = db.session.get(Payment, payment_id) or abort(404)
    return send_receipt(payment)


@payments_bp.post("/<int:payment_id>/reverse")
@admin_required
def reverse(payment_id):
    payment = db.session.get(Payment, payment_id) or abort(404)
    form = ReversePaymentForm()
    if not form.validate_on_submit():
        flash("A reason is required to reverse a payment.", "danger")
        return redirect(url_for("payments.view_payment", payment_id=payment.id))
    try:
        payment_service.reverse_payment(payment, form.reason.data, reversed_by=current_user)
    except payment_service.PaymentError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    else:
        audit_service.log_action(
            "payment.reverse",
            "payment",
            payment.id,
            {"reason": form.reason.data},
        )
        db.session.commit()
        flash("Payment reversed and balance restored.", "success")
    return redirect(url_for("payments.view_payment", payment_id=payment.id))
