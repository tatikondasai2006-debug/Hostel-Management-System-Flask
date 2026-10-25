"""Fee management routes."""

from __future__ import annotations

from datetime import date

from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy import or_, select

from app.constants import (
    FEE_OVERDUE,
    FEE_PAID,
    FEE_PARTIAL,
    FEE_PENDING,
    ROOM_TYPE_LABELS,
)
from app.extensions import db
from app.models import FeeStructure, Student, StudentFee
from app.services import audit_service, fee_service
from app.utils.decorators import admin_required, flash_form_errors
from app.utils.pagination import page_args, query_string_without_page

from . import fees_bp
from .forms import FeeAdjustForm, FeeStructureForm, GenerateFeesForm


@fees_bp.route("/")
@admin_required
def list_fees():
    page, per_page = page_args(20)
    stmt = select(StudentFee).join(Student, Student.id == StudentFee.student_id)

    search = (request.args.get("q") or "").strip()
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Student.full_name.ilike(like), Student.roll_number.ilike(like)))
    if request.args.get("period"):
        stmt = stmt.where(StudentFee.billing_period == request.args["period"])
    status = request.args.get("status")
    if status in {FEE_PENDING, FEE_PARTIAL, FEE_PAID}:
        stmt = stmt.where(StudentFee.status == status)
    elif status == FEE_OVERDUE:
        stmt = stmt.where(
            StudentFee.amount_paid < StudentFee.total_amount,
            StudentFee.due_date < date.today(),
        )

    stmt = stmt.order_by(StudentFee.billing_period.desc(), Student.roll_number)
    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)

    periods = [
        row[0]
        for row in db.session.execute(
            select(StudentFee.billing_period).distinct().order_by(StudentFee.billing_period.desc())
        ).all()
    ]
    totals = {
        "billed": sum((f.total_amount for f in pagination.items), 0),
        "collected": sum((f.amount_paid for f in pagination.items), 0),
    }
    return render_template(
        "fees/list.html",
        pagination=pagination,
        fees=pagination.items,
        periods=periods,
        filters=request.args,
        query_string=query_string_without_page(),
        totals=totals,
    )


@fees_bp.route("/<int:fee_id>")
@admin_required
def view_fee(fee_id):
    fee = db.session.get(StudentFee, fee_id) or abort(404)
    return render_template("fees/detail.html", fee=fee, adjust_form=FeeAdjustForm(obj=fee))


@fees_bp.route("/generate", methods=["GET", "POST"])
@admin_required
def generate():
    form = GenerateFeesForm()
    if request.method == "GET":
        form.billing_period.data = date.today().strftime("%Y-%m")
    if form.validate_on_submit():
        period = form.billing_period.data
        student_ids = None
        if form.scope.data == "allocated":
            from app.constants import ALLOCATION_ACTIVE
            from app.models import RoomAllocation

            student_ids = list(
                db.session.execute(
                    select(RoomAllocation.student_id).where(
                        RoomAllocation.status == ALLOCATION_ACTIVE
                    )
                ).scalars()
            )
            if not student_ids:
                flash("No students are currently allocated a room.", "warning")
                return render_template("fees/generate.html", form=form)
        result = fee_service.generate_fees_for_period(
            period,
            due_date=form.due_date.data,
            student_ids=student_ids,
        )
        audit_service.log_action(
            "fee.generate",
            "student_fee",
            None,
            {"period": period, "created": len(result["created"])},
        )
        db.session.commit()
        flash(
            f"Generated {len(result['created'])} bill(s) for {period}; "
            f"{len(result['skipped'])} skipped (already billed).",
            "success" if result["created"] else "info",
        )
        return redirect(url_for("fees.list_fees", period=period))
    elif form.is_submitted():
        flash_form_errors(form)
    return render_template("fees/generate.html", form=form)


@fees_bp.post("/<int:fee_id>/adjust")
@admin_required
def adjust(fee_id):
    fee = db.session.get(StudentFee, fee_id) or abort(404)
    form = FeeAdjustForm(obj=fee)
    if form.validate_on_submit():
        fee.other_amount = form.other_amount.data
        fee.discount_amount = form.discount_amount.data
        if form.notes.data:
            fee.notes = form.notes.data
        fee_service.recompute_totals(fee)
        if fee.amount_paid > fee.total_amount:
            db.session.rollback()
            flash(
                "Adjustment would make the total lower than the amount already paid.",
                "danger",
            )
            return redirect(url_for("fees.view_fee", fee_id=fee.id))
        audit_service.log_action("fee.adjust", "student_fee", fee.id)
        db.session.commit()
        flash("Bill updated.", "success")
    else:
        flash_form_errors(form)
    return redirect(url_for("fees.view_fee", fee_id=fee.id))


@fees_bp.post("/<int:fee_id>/recalculate")
@admin_required
def recalculate(fee_id):
    fee = db.session.get(StudentFee, fee_id) or abort(404)
    fee_service.recompute_totals(fee)
    audit_service.log_action("fee.recalculate", "student_fee", fee.id)
    db.session.commit()
    flash("Late fee and status recalculated.", "success")
    return redirect(url_for("fees.view_fee", fee_id=fee.id))


@fees_bp.post("/apply-late-fees")
@admin_required
def apply_late_fees():
    changed = fee_service.apply_late_fees()
    audit_service.log_action("fee.late_fees", "student_fee", None, {"changed": changed})
    db.session.commit()
    flash(f"Recomputed {changed} unpaid bill(s).", "success")
    return redirect(url_for("fees.list_fees"))


# ---------------------------------------------------------------------------
# Fee structures
# ---------------------------------------------------------------------------
@fees_bp.route("/structures")
@admin_required
def structures():
    records = (
        db.session.execute(select(FeeStructure).order_by(FeeStructure.room_type)).scalars().all()
    )
    return render_template("fees/structures.html", structures=records)


@fees_bp.route("/structures/<int:structure_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_structure(structure_id):
    structure = db.session.get(FeeStructure, structure_id) or abort(404)
    form = FeeStructureForm(obj=structure)
    if form.validate_on_submit():
        structure.monthly_amount = form.monthly_amount.data
        structure.mess_amount = form.mess_amount.data
        structure.laundry_amount = form.laundry_amount.data
        structure.maintenance_amount = form.maintenance_amount.data
        structure.description = form.description.data
        audit_service.log_action("fee_structure.update", "fee_structure", structure.id)
        db.session.commit()
        flash("Fee structure updated.", "success")
        return redirect(url_for("fees.structures"))
    elif form.is_submitted():
        flash_form_errors(form)
    return render_template(
        "fees/structure_form.html",
        form=form,
        structure=structure,
        label=ROOM_TYPE_LABELS.get(structure.room_type, structure.room_type),
    )
