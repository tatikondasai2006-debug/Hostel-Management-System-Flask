"""Authentication routes: signup, login, logout."""

from __future__ import annotations

from datetime import UTC, datetime

from flask import (
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.constants import ROLE_ADMIN, ROLE_STUDENT, STUDENT_ACTIVE
from app.extensions import db, limiter
from app.models import Student, User
from app.services import audit_service
from app.utils.decorators import (
    flash_form_errors,
    is_safe_url,
)

from . import auth_bp
from .forms import LoginForm, SignupForm


def _home_for(user) -> str:
    return "admin.dashboard" if user.role == ROLE_ADMIN else "portal.dashboard"


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config["RATELIMIT_LOGIN"], methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(_home_for(current_user)))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = db.session.execute(select(User).where(User.email == email)).scalar_one_or_none()

        # Generic error message avoids account enumeration.
        if user is None or not user.check_password(form.password.data):
            flash("Invalid email or password.", "danger")
        elif not user.is_active:
            flash("This account has been deactivated. Contact the administrator.", "warning")
        else:
            login_user(user, remember=form.remember.data)
            user.last_login_at = datetime.now(UTC)
            audit_service.log_action("login", "user", user.id, {"role": user.role}, actor=user)
            db.session.commit()
            flash("Welcome back!", "success")
            next_url = request.args.get("next")
            if next_url and is_safe_url(next_url):
                return redirect(next_url)
            return redirect(url_for(_home_for(user)))
    elif request.method == "POST":
        flash_form_errors(form)

    return render_template("auth/login.html", form=form)


@auth_bp.route("/signup", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config["RATELIMIT_SIGNUP"], methods=["POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for(_home_for(current_user)))

    form = SignupForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        roll_number = form.roll_number.data.strip()

        # Pre-check for friendly errors; the DB unique constraints remain the
        # authoritative guard against concurrent duplicate submissions.
        if db.session.execute(select(User).where(User.email == email)).scalar_one_or_none():
            flash("An account with that email already exists.", "danger")
            return render_template("auth/signup.html", form=form), 409
        if db.session.execute(
            select(Student).where(Student.roll_number == roll_number)
        ).scalar_one_or_none():
            flash("That roll number is already registered.", "danger")
            return render_template("auth/signup.html", form=form), 409

        user = User(email=email, role=ROLE_STUDENT, is_active=True)
        user.set_password(form.password.data)
        student = Student(
            user=user,
            full_name=form.full_name.data.strip(),
            email=email,
            phone=form.phone.data.strip(),
            roll_number=roll_number,
            course=form.course.data.strip(),
            academic_year=form.academic_year.data.strip(),
            address=form.address.data,
            emergency_contact=form.emergency_contact.data,
            status=STUDENT_ACTIVE,
        )
        db.session.add(user)
        db.session.add(student)
        try:
            db.session.flush()
            audit_service.log_action(
                "student.register", "student", student.id, {"roll": roll_number}
            )
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("That email or roll number is already registered.", "danger")
            return render_template("auth/signup.html", form=form), 409

        login_user(user)
        flash("Your account has been created.", "success")
        return redirect(url_for("portal.dashboard"))
    elif request.method == "POST":
        flash_form_errors(form)

    return render_template("auth/signup.html", form=form)


@auth_bp.post("/logout")
@login_required
def logout():
    user = current_user
    audit_service.log_action("logout", "user", user.id, actor=user)
    db.session.commit()
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))
