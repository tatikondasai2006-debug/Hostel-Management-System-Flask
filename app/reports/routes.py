"""Report viewing and export routes."""

from __future__ import annotations

from datetime import datetime

from flask import Response, abort, render_template, request

from app.services import report_pdf_service, report_service
from app.utils.csv_utils import csv_response, safe_filename
from app.utils.decorators import admin_required

from . import reports_bp


def _filters() -> dict:
    data = {k: v for k, v in request.args.items() if v}
    for key in ("start_date", "end_date"):
        if key in data:
            try:
                data[key] = datetime.strptime(data[key], "%Y-%m-%d").date()
            except ValueError:
                data.pop(key, None)
    return data


@reports_bp.route("/")
@admin_required
def index():
    reports = [
        {"slug": slug, "title": meta["title"]} for slug, meta in report_service.REPORTS.items()
    ]
    return render_template("reports/index.html", reports=reports)


@reports_bp.route("/<slug>")
@admin_required
def view(slug):
    if slug not in report_service.REPORTS:
        abort(404)
    report = report_service.build_report(slug, _filters())
    return render_template("reports/view.html", report=report, filters=request.args)


@reports_bp.route("/<slug>/export.csv")
@admin_required
def export_csv(slug):
    if slug not in report_service.REPORTS:
        abort(404)
    report = report_service.build_report(slug, _filters())
    filename = safe_filename("hostel", slug)
    return csv_response(report["rows"], report["headers"], filename)


@reports_bp.route("/occupancy.pdf")
@admin_required
def occupancy_pdf():
    pdf = report_pdf_service.occupancy_pdf()
    response = Response(pdf, mimetype="application/pdf")
    response.headers["Content-Disposition"] = 'attachment; filename="room-occupancy.pdf"'
    return response


@reports_bp.route("/financial.pdf")
@admin_required
def financial_pdf():
    pdf = report_pdf_service.financial_summary_pdf()
    response = Response(pdf, mimetype="application/pdf")
    response.headers["Content-Disposition"] = 'attachment; filename="financial-summary.pdf"'
    return response
