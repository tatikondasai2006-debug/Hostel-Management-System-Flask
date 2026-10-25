"""Application factory for the Hostel Management System."""

from __future__ import annotations

import logging
import os
from datetime import date, datetime

from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import HTTPException

from app.constants import ROLE_ADMIN
from app.extensions import csrf, db, limiter, login_manager, migrate
from app.utils.money import format_currency
from config import get_config


def create_app(config_object=None) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_object or get_config())

    _configure_logging(app)
    _ensure_instance_folder(app)
    _register_extensions(app)
    _register_blueprints(app)
    _register_cli(app)
    _register_context(app)
    _register_error_handlers(app)
    _register_root_routes(app)
    _register_user_loader(app)

    return app


def _configure_logging(app: Flask) -> None:
    level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    app.logger.setLevel(level)


def _ensure_instance_folder(app: Flask) -> None:
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if uri.startswith("sqlite"):
        os.makedirs(app.instance_path, exist_ok=True)


def _register_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(
        app, db, directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations")
    )
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)


def _register_blueprints(app: Flask) -> None:
    from app.admin import admin_bp
    from app.allocations import allocations_bp
    from app.auth import auth_bp
    from app.fees import fees_bp
    from app.payments import payments_bp
    from app.reports import reports_bp
    from app.rooms import hostels_bp, rooms_bp
    from app.students import portal_bp, students_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(portal_bp)
    app.register_blueprint(hostels_bp)
    app.register_blueprint(rooms_bp)
    app.register_blueprint(allocations_bp)
    app.register_blueprint(fees_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(reports_bp)


def _register_cli(app: Flask) -> None:
    from app.cli import register_cli

    register_cli(app)


def _register_user_loader(app: Flask) -> None:
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None


def _register_context(app: Flask) -> None:
    from app.services import settings_service

    @app.template_filter("money")
    def money_filter(value):
        try:
            symbol = settings_service.get_currency_symbol()
        except Exception:  # pragma: no cover - outside request context
            symbol = ""
        return format_currency(value, symbol)

    @app.template_filter("datetime")
    def datetime_filter(value, fmt: str = "%d %b %Y, %H:%M"):
        if not value:
            return "—"
        if isinstance(value, str):
            return value
        return value.strftime(fmt)

    @app.template_filter("date")
    def date_filter(value, fmt: str = "%d %b %Y"):
        if not value:
            return "—"
        if isinstance(value, str):
            return value
        return value.strftime(fmt)

    @app.template_filter("status_class")
    def status_class(value):
        mapping = {
            "active": "success",
            "paid": "success",
            "completed": "success",
            "available": "success",
            "inactive": "secondary",
            "released": "secondary",
            "archived": "secondary",
            "pending": "warning",
            "partial": "info",
            "partial pay": "info",
            "overdue": "danger",
            "full": "danger",
            "maintenance": "warning",
            "unavailable": "dark",
            "reversed": "danger",
        }
        return mapping.get(str(value).lower(), "secondary")

    @app.context_processor
    def inject_globals():
        try:
            identity = settings_service.get_hostel_identity()
            currency = settings_service.get_currency_symbol()
        except Exception:  # pragma: no cover
            identity = {"name": "Hostel", "address": "", "contact": "", "email": ""}
            currency = ""
        return {
            "hostel_identity": identity,
            "currency_symbol": currency,
            "current_year": date.today().year,
            "now": datetime.now(),
        }


def _register_error_handlers(app: Flask) -> None:
    def wants_json() -> bool:
        return request.path.startswith("/api/") or (
            request.accept_mimetypes.best == "application/json"
        )

    @app.errorhandler(CSRFError)
    def handle_csrf(error):
        if wants_json():
            return jsonify(error="CSRF validation failed"), 400
        return render_template("errors/400.html", message=error.description), 400

    @app.errorhandler(403)
    def forbidden(error):
        if wants_json():
            return jsonify(error="Forbidden"), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        if wants_json():
            return jsonify(error="Not found"), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        if wants_json():
            return jsonify(error="Method not allowed"), 405
        return render_template("errors/400.html", message="Method not allowed."), 405

    @app.errorhandler(500)
    def server_error(error):  # pragma: no cover - exercised manually
        db.session.rollback()
        app.logger.exception("Unhandled server error")
        if wants_json():
            return jsonify(error="Internal server error"), 500
        return render_template("errors/500.html"), 500

    @app.errorhandler(Exception)
    def unhandled(error):  # pragma: no cover - exercised manually
        if isinstance(error, HTTPException):
            return error
        db.session.rollback()
        app.logger.exception("Unhandled exception")
        if wants_json():
            return jsonify(error="Internal server error"), 500
        return render_template("errors/500.html"), 500


def _register_root_routes(app: Flask) -> None:
    @app.route("/")
    def index():
        if current_user.is_authenticated:
            if current_user.role == ROLE_ADMIN:
                return redirect(url_for("admin.dashboard"))
            return redirect(url_for("portal.dashboard"))
        return redirect(url_for("auth.login"))

    @app.route("/healthz")
    def healthz():
        try:
            db.session.execute(db.text("SELECT 1"))
            db_ok = True
        except Exception:  # pragma: no cover
            db_ok = False
        status = 200 if db_ok else 503
        return jsonify(status="ok" if db_ok else "degraded", database=db_ok), status
