"""Administrator student-management routes."""

from __future__ import annotations

from datetime import date

from flask import (
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.constants import (
    ALLOCATION_ACTIVE,
    ROLE_STUDENT,
    STUDENT_ACTIVE,
    STUDENT_ARCHIVED,
    STUDENT_STATUSES,
)
from app.extensions import db
from app.models import Payment, RoomAllocation, Student, StudentFee, User
from app.services import allocation_service, audit_service
from app.utils.decorators import admin_required, flash_form_errors
from app.utils.pagination import page_args, query_string_without_page

from . import students_bp
from .forms import StudentForm


def _apply_filters(stmt, args):
    search = (args.get("q") or "").strip()
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                Student.full_name.ilike(like),
                Student.roll_number.ilike(like),
                Student.email.ilike(like),
                Student.phone.ilike(like),
            )
        )
    if args.get("course"):
        stmt = stmt.where(Student.course == args["course"])
    if args.get("academic_year"):
        stmt = stmt.where(Student.academic_year == args["academic_year"])
    if args.get("status") in STUDENT_STATUSES:
        stmt = stmt.where(Student.status == args["status"])

    allocation_state = args.get("allocation")
    active_alloc = select(RoomAllocation.student_id).where(
        RoomAllocation.status == ALLOCATION_ACTIVE
    )
    if allocation_state == "allocated":
        stmt = stmt.where(Student.id.in_(active_alloc))
    elif allocation_state == "unallocated":
        stmt = stmt.where(Student.id.notin_(active_alloc))

    fee_state = args.get("fee_status")
    has_fees = select(StudentFee.student_id).where(StudentFee.student_id == Student.id)
    outstanding = select(StudentFee.student_id).where(
        StudentFee.student_id == Student.id,
        StudentFee.amount_paid < StudentFee.total_amount,
    )
    overdue = select(StudentFee.student_id).where(
        StudentFee.student_id == Student.id,
        StudentFee.amount_paid < StudentFee.total_amount,
        StudentFee.due_date < date.today(),
    )
    if fee_state == "paid":
        stmt = stmt.where(Student.id.in_(has_fees), Student.id.notin_(outstanding))
    elif fee_state == "due":
        stmt = stmt.where(Student.id.in_(outstanding), Student.id.notin_(overdue))
    elif fee_state == "overdue":
        stmt = stmt.where(Student.id.in_(overdue))
    elif fee_state == "none":
        stmt = stmt.where(Student.id.notin_(has_fees))
    return stmt


@students_bp.route("/")
@admin_required
def list_students():
    page, per_page = page_args()
    stmt = select(Student)
    stmt = _apply_filters(stmt, request.args)
    stmt = stmt.order_by(Student.roll_number)
    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)

    courses = [
        row[0]
        for row in db.session.execute(
            select(Student.course).distinct().order_by(Student.course)
        ).all()
    ]
    years = [
        row[0]
        for row in db.session.execute(
            select(Student.academic_year).distinct().order_by(Student.academic_year)
        ).all()
    ]
    return render_template(
        "students/list.html",
        pagination=pagination,
        students=pagination.items,
        courses=courses,
        years=years,
        filters=request.args,
        query_string=query_string_without_page(),
    )


@students_bp.route("/new", methods=["GET", "POST"])
@admin_required
def create_student():
    form = StudentForm()
    if request.method == "GET":
        form.admission_date.data = date.today()
        form.status.data = STUDENT_ACTIVE
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        student = Student(
            full_name=form.full_name.data.strip(),
            email=email,
            phone=form.phone.data.strip(),
            roll_number=form.roll_number.data.strip(),
            course=form.course.data.strip(),
            academic_year=form.academic_year.data.strip(),
            address=form.address.data,
            emergency_contact=form.emergency_contact.data,
            admission_date=form.admission_date.data,
            status=form.status.data,
        )
        if form.create_login.data or form.password.data:
            if not form.password.data:
                flash("Provide a password to create a portal login.", "danger")
                return render_template("students/form.html", form=form, student=None)
            user = User(email=email, role=ROLE_STUDENT, is_active=True)
            user.set_password(form.password.data)
            student.user = user
            db.session.add(user)
        db.session.add(student)
        try:
            db.session.flush()
            audit_service.log_action(
                "student.create", "student", student.id, {"roll": student.roll_number}
            )
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("A student with that email or roll number already exists.", "danger")
            return render_template("students/form.html", form=form, student=None)
        flash("Student record created.", "success")
        return redirect(url_for("students.view_student", student_id=student.id))
    elif request.method == "POST":
        flash_form_errors(form)

    return render_template("students/form.html", form=form, student=None)


def _get_student_or_404(student_id: int) -> Student:
    student = db.session.get(Student, student_id)
    if student is None:
        abort(404)
    return student


@students_bp.route("/<int:student_id>")
@admin_required
def view_student(student_id):
    student = _get_student_or_404(student_id)
    payments = (
        db.session.execute(
            select(Payment).where(Payment.student_id == student.id).order_by(Payment.paid_at.desc())
        )
        .scalars()
        .all()
    )
    allocations = (
        db.session.execute(
            select(RoomAllocation)
            .where(RoomAllocation.student_id == student.id)
            .order_by(RoomAllocation.allocated_at.desc())
        )
        .scalars()
        .all()
    )
    fees = (
        db.session.execute(
            select(StudentFee)
            .where(StudentFee.student_id == student.id)
            .order_by(StudentFee.billing_period.desc())
        )
        .scalars()
        .all()
    )
    return render_template(
        "students/detail.html",
        student=student,
        payments=payments,
        allocations=allocations,
        fees=fees,
    )


@students_bp.route("/<int:student_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_student(student_id):
    student = _get_student_or_404(student_id)
    form = StudentForm(obj=student, student=student)
    if request.method == "GET":
        form.create_login.data = student.user is not None
    if form.validate_on_submit():
        student.full_name = form.full_name.data.strip()
        new_email = form.email.data.strip().lower()
        student.email = new_email
        student.phone = form.phone.data.strip()
        student.roll_number = form.roll_number.data.strip()
        student.course = form.course.data.strip()
        student.academic_year = form.academic_year.data.strip()
        student.address = form.address.data
        student.emergency_contact = form.emergency_contact.data
        student.admission_date = form.admission_date.data
        student.status = form.status.data

        if form.password.data:
            if student.user is None:
                user = User(email=new_email, role=ROLE_STUDENT, is_active=True)
                user.set_password(form.password.data)
                student.user = user
                db.session.add(user)
            else:
                student.user.set_password(form.password.data)
                student.user.email = new_email
            student.user.is_active = form.status.data != STUDENT_ARCHIVED

        try:
            audit_service.log_action(
                "student.update",
                "student",
                student.id,
                {"status": student.status},
            )
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("That email or roll number is already in use.", "danger")
            return render_template("students/form.html", form=form, student=student)
        flash("Student record updated.", "success")
        return redirect(url_for("students.view_student", student_id=student.id))
    elif request.method == "POST":
        flash_form_errors(form)

    return render_template("students/form.html", form=form, student=student)


@students_bp.post("/<int:student_id>/status")
@admin_required
def change_status(student_id):
    student = _get_student_or_404(student_id)
    new_status = (request.form.get("status") or "").strip()
    if new_status not in STUDENT_STATUSES:
        flash("Invalid status.", "danger")
        return redirect(url_for("students.view_student", student_id=student.id))

    if new_status != STUDENT_ACTIVE:
        current = student.current_allocation
        if current is not None:
            try:
                allocation_service.release_allocation(
                    current,
                    reason="deactivation",
                    released_by=current_user,
                )
            except allocation_service.AllocationError as exc:
                db.session.rollback()
                flash(f"Could not release room: {exc}", "danger")
                return redirect(url_for("students.view_student", student_id=student.id))

    student.status = new_status
    if student.user is not None:
        student.user.is_active = new_status == STUDENT_ACTIVE
    audit_service.log_action("student.status_change", "student", student.id, {"status": new_status})
    db.session.commit()
    flash(f"Student marked as {new_status}.", "success")
    return redirect(url_for("students.view_student", student_id=student.id))
