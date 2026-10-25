"""Room and hostel blueprints."""

from flask import Blueprint

rooms_bp = Blueprint("rooms", __name__, url_prefix="/rooms")
hostels_bp = Blueprint("hostels", __name__, url_prefix="/hostels")

from app.rooms import routes  # noqa: E402,F401
