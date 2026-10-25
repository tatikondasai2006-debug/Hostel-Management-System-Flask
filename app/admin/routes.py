"""Administrator dashboard, settings and audit log."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from flask import render_template, request
from sqlalchemy import select

from app.constants import (
    SETTING_CURRENCY_SYMBOL,
    SETTING_HOSTEL_ADDRESS,
    SETTING_HOSTEL_CONTACT,
    SETTING_HOSTEL_EMAIL,
    SETTING_HOSTEL_NAME,
    SETTING_LATE_FEE_GRACE_DAYS,
    SETTING_LATE_FEE_PERCENT,
)
from app.extensions import db
from app.models import AuditLog
from app.services import audit_service, dashboard_service, settings_service
from app.utils.decorators import admin_required, flash_form_errors
from app.utils.pagination import page_args, query_string_without_page

from . import admin_bp
from .forms import SettingsForm


@admin_bp.route("/")
@admin_required
def dashboard():
    stats = dashboard_service.admin_dashboard_stats()
    charts = {
        "byRoomType": dashboard_service.occupancy_by_room_type(),
        "byHostel": dashboard_service.occupancy_by_hostel(),
        "monthlyTrend": dashboard_service.monthly_payment_trend(6),
        "paidVsPending": dashboard_service.paid_vs_pending(),
    }
    return render_template("admin/dashboard.html", stats=stats, charts_json=json.dumps(charts))


@admin_bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    form = SettingsForm()
    if request.method == "GET":
        form.hostel_name.data = settings_service.get_setting(SETTING_HOSTEL_NAME)
        form.hostel_address.data = settings_service.get_setting(SETTING_HOSTEL_ADDRESS)
        form.hostel_contact.data = settings_service.get_setting(SETTING_HOSTEL_CONTACT)
        form.hostel_email.data = settings_service.get_setting(SETTING_HOSTEL_EMAIL)
        form.currency_symbol.data = settings_service.get_setting(SETTING_CURRENCY_SYMBOL)
        percent = settings_service.get_setting(SETTING_LATE_FEE_PERCENT)
        try:
            form.late_fee_percent.data = Decimal(str(percent))
        except (InvalidOperation, TypeError, ValueError):
            form.late_fee_percent.data = None
        grace = settings_service.get_setting(SETTING_LATE_FEE_GRACE_DAYS)
        try:
            form.late_fee_grace_days.data = int(float(grace))
        except (TypeError, ValueError):
            form.late_fee_grace_days.data = None
    if form.validate_on_submit():
        settings_service.set_setting(SETTING_HOSTEL_NAME, form.hostel_name.data.strip())
        settings_service.set_setting(SETTING_HOSTEL_ADDRESS, form.hostel_address.data or "")
        settings_service.set_setting(SETTING_HOSTEL_CONTACT, form.hostel_contact.data or "")
        settings_service.set_setting(SETTING_HOSTEL_EMAIL, form.hostel_email.data or "")
        settings_service.set_setting(SETTING_CURRENCY_SYMBOL, form.currency_symbol.data.strip())
        settings_service.set_setting(SETTING_LATE_FEE_PERCENT, str(form.late_fee_percent.data))
        settings_service.set_setting(
            SETTING_LATE_FEE_GRACE_DAYS, str(form.late_fee_grace_days.data)
        )
        audit_service.log_action("settings.update", "setting", None)
        db.session.commit()
        settings_service.clear_cache()
        from flask import flash

        flash("Settings saved.", "success")
    elif form.is_submitted():
        flash_form_errors(form)
    return render_template("settings/edit.html", form=form)


@admin_bp.route("/audit")
@admin_required
def audit_log():
    page, per_page = page_args(25)
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if request.args.get("action"):
        stmt = stmt.where(AuditLog.action == request.args["action"])
    if request.args.get("entity_type"):
        stmt = stmt.where(AuditLog.entity_type == request.args["entity_type"])
    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)
    actions = [
        row[0]
        for row in db.session.execute(
            select(AuditLog.action).distinct().order_by(AuditLog.action)
        ).all()
    ]
    entities = [
        row[0]
        for row in db.session.execute(
            select(AuditLog.entity_type).distinct().order_by(AuditLog.entity_type)
        ).all()
    ]
    return render_template(
        "audit/list.html",
        pagination=pagination,
        logs=pagination.items,
        actions=actions,
        entities=entities,
        filters=request.args,
        query_string=query_string_without_page(),
    )
