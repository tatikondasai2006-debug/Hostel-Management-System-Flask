"""PDF report generation (ReportLab) for occupancy and financial summaries."""

from __future__ import annotations

import io
from datetime import UTC, datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services import settings_service
from app.utils.money import money


def _styles():
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("ReportTitle", parent=styles["Title"], fontSize=16, spaceAfter=2),
        "meta": ParagraphStyle(
            "Meta",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#6b7280"),
        ),
    }


def _build(title: str, headers, rows, subtitle: str = "", landscape_mode: bool = False) -> bytes:
    identity = settings_service.get_hostel_identity()
    styles = _styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4) if landscape_mode else A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=title,
    )
    story = [
        Paragraph(identity["name"], styles["title"]),
        Paragraph(title, ParagraphStyle("Sub", parent=styles["title"], fontSize=12)),
        Paragraph(
            f"{subtitle} &nbsp;|&nbsp; Generated "
            f"{datetime.now(UTC).strftime('%d %b %Y %H:%M UTC')}",
            styles["meta"],
        ),
        Spacer(1, 10),
    ]

    data = (
        [headers]
        + [
            [str(row.get(h, "")) for h in headers]
            if isinstance(row, dict)
            else [str(value) for value in row]
            for row in rows
        ]
        if rows
        else [headers, ["No data"] + [""] * (len(headers) - 1)]
    )

    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2d3d")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d1d5db")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return buffer.getvalue()


def occupancy_pdf() -> bytes:
    from app.services import report_service

    headers, rows = report_service.room_occupancy()
    return _build(
        "Room Occupancy Report",
        headers,
        rows,
        subtitle=f"{len(rows)} rooms",
        landscape_mode=True,
    )


def financial_summary_pdf() -> bytes:
    from app.services import report_service

    headers, rows = report_service.fee_collection()
    total_billed = sum(money(r["Total"]) for r in rows)
    total_paid = sum(money(r["Paid"]) for r in rows)
    total_balance = sum(money(r["Balance"]) for r in rows)
    subtitle = (
        f"Billed {money(total_billed):,.2f} | Collected {money(total_paid):,.2f} | "
        f"Outstanding {money(total_balance):,.2f}"
    )
    return _build(
        "Financial Summary Report",
        headers,
        rows,
        subtitle=subtitle,
        landscape_mode=True,
    )
