"""Student management (admin) + student portal blueprints."""

from flask import Blueprint

students_bp = Blueprint("students", __name__, url_prefix="/students")
portal_bp = Blueprint("portal", __name__, url_prefix="/portal")

from app.students import portal, routes  # noqa: E402,F401
