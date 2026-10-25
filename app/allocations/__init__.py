"""Room allocation blueprint."""

from flask import Blueprint

allocations_bp = Blueprint("allocations", __name__, url_prefix="/allocations")

from app.allocations import routes  # noqa: E402,F401
