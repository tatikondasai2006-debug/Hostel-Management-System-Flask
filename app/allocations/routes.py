"""Automatic + manual room allocation routes."""

from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import select

from app.constants import (
    ALLOCATION_ACTIVE,
    ALLOCATION_STATUSES,
)
from app.extensions import db
from app.models import Hostel, Room, RoomAllocation, Student
from app.services import allocation_service, audit_service
from app.utils.decorators import admin_required, flash_form_errors
from app.utils.pagination import page_args, query_string_without_page

from . import allocations_bp
from .forms import AutoAllocateForm, ManualAssignForm, ReleaseForm, TransferForm


@allocations_bp.route("/")
@admin_required
def list_allocations():
    page, per_page = page_args(20)
    stmt = select(RoomAllocation).join(Room, Room.id == RoomAllocation.room_id)

    status = request.args.get("status")
    if status in ALLOCATION_STATUSES:
        stmt = stmt.where(RoomAllocation.status == status)
    if request.args.get("room_id"):
        stmt = stmt.where(RoomAllocation.room_id == int(request.args["room_id"]))
    if request.args.get("hostel_id"):
        stmt = stmt.where(Room.hostel_id == int(request.args["hostel_id"]))
    search = (request.args.get("q") or "").strip()
    if search:
        stmt = stmt.join(Student, Student.id == RoomAllocation.student_id).where(
            Student.full_name.ilike(f"%{search}%")
        )

    stmt = stmt.order_by(RoomAllocation.allocated_at.desc())
    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)
    hostels = db.session.execute(select(Hostel).order_by(Hostel.name)).scalars().all()
    return render_template(
        "allocations/list.html",
        pagination=pagination,
        allocations=pagination.items,
        hostels=hostels,
        filters=request.args,
        query_string=query_string_without_page(),
    )


@allocations_bp.route("/new", methods=["GET", "POST"])
@admin_required
def auto_allocate():
    form = AutoAllocateForm()
    if form.validate_on_submit():
        student = db.session.get(Student, form.student_id.data) or abort(404)
        room_type = form.room_type.data or None
        try:
            allocation = allocation_service.allocate_bed(
                student,
                room_type=room_type,
                allocated_by=current_user,
                notes=form.notes.data,
            )
        except allocation_service.AllocationError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        else:
            audit_service.log_action(
                "allocation.auto",
                "room_allocation",
                allocation.id,
                {"student": student.id, "room": allocation.room_id},
            )
            db.session.commit()
            flash(
                f"Allocated {student.full_name} to room "
                f"{allocation.room.room_number} (bed {allocation.bed_index}).",
                "success",
            )
            return redirect(url_for("students.view_student", student_id=student.id))
    elif form.is_submitted():
        flash_form_errors(form)
    return render_template("allocations/auto.html", form=form)


@allocations_bp.route("/manual", methods=["GET", "POST"])
@admin_required
def manual_assign():
    form = ManualAssignForm()
    if form.validate_on_submit():
        student = db.session.get(Student, form.student_id.data) or abort(404)
        try:
            allocation = allocation_service.transfer_student(
                student,
                form.room_id.data,
                allocated_by=current_user,
                notes=form.notes.data,
            )
        except allocation_service.AllocationError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        else:
            audit_service.log_action(
                "allocation.manual",
                "room_allocation",
                allocation.id,
                {"student": student.id, "room": allocation.room_id},
            )
            db.session.commit()
            flash(
                f"Assigned {student.full_name} to room {allocation.room.room_number}.",
                "success",
            )
            return redirect(url_for("students.view_student", student_id=student.id))
    elif form.is_submitted():
        flash_form_errors(form)
    return render_template("allocations/manual.html", form=form)


@allocations_bp.route("/student/<int:student_id>/transfer", methods=["GET", "POST"])
@admin_required
def transfer(student_id):
    student = db.session.get(Student, student_id) or abort(404)
    current = student.current_allocation
    form = TransferForm(exclude_room_id=current.room_id if current else None)
    if form.validate_on_submit():
        try:
            allocation = allocation_service.transfer_student(
                student,
                form.room_id.data,
                allocated_by=current_user,
                notes=form.notes.data,
            )
        except allocation_service.AllocationError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        else:
            audit_service.log_action(
                "allocation.transfer",
                "room_allocation",
                allocation.id,
                {"student": student.id, "room": allocation.room_id},
            )
            db.session.commit()
            flash(
                f"{student.full_name} transferred to room {allocation.room.room_number}.",
                "success",
            )
            return redirect(url_for("students.view_student", student_id=student.id))
    elif form.is_submitted():
        flash_form_errors(form)
    return render_template("allocations/transfer.html", form=form, student=student, current=current)


@allocations_bp.post("/<int:allocation_id>/release")
@admin_required
def release(allocation_id):
    allocation = db.session.get(RoomAllocation, allocation_id) or abort(404)
    form = ReleaseForm()
    if not form.validate_on_submit():
        flash("Invalid request.", "danger")
        return redirect(url_for("students.view_student", student_id=allocation.student_id))
    if allocation.status != ALLOCATION_ACTIVE:
        flash("This allocation is already released.", "warning")
        return redirect(url_for("students.view_student", student_id=allocation.student_id))
    allocation_service.release_allocation(
        allocation,
        reason=form.reason.data or "admin",
        released_by=current_user,
    )
    audit_service.log_action(
        "allocation.release",
        "room_allocation",
        allocation.id,
        {"student": allocation.student_id, "room": allocation.room_id},
    )
    db.session.commit()
    flash("Bed released.", "success")
    return redirect(url_for("students.view_student", student_id=allocation.student_id))
