"""Fee management blueprint."""

from flask import Blueprint

fees_bp = Blueprint("fees", __name__, url_prefix="/fees")

from app.fees import routes  # noqa: E402,F401
