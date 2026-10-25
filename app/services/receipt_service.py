"""PDF payment receipt generation (ReportLab)."""

from __future__ import annotations

import io
from datetime import UTC, datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.constants import PAYMENT_METHOD_LABELS
from app.services import settings_service
from app.utils.money import money, to_decimal


def _fmt(value) -> str:
    return f"{money(value):,.2f}"


def _as_datetime(value) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.now(UTC)


def build_receipt_pdf(payment) -> bytes:
    """Render a professional, printable receipt for ``payment`` as PDF bytes."""
    identity = settings_service.get_hostel_identity()
    currency = settings_service.get_currency_symbol()
    student = payment.student
    fee = payment.fee

    room = getattr(fee, "room", None)
    room_number = room.room_number if room else "—"
    room_label = room.room_type.title() if room and room.room_type else "—"
    if room and room.hostel:
        room_number = f"{room.hostel.name} / {room.room_number}"

    paid_amount = to_decimal(payment.amount)
    balance_after = to_decimal(fee.balance)
    previous_balance = money(
        to_decimal(fee.total_amount) - (to_decimal(fee.amount_paid) - paid_amount)
    )

    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "ReceiptTitle",
        parent=styles["Title"],
        fontSize=18,
        spaceAfter=2,
        textColor=colors.HexColor("#1f2d3d"),
    )
    subtitle = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#6b7280"),
    )
    h2 = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontSize=11,
        textColor=colors.HexColor("#1f2d3d"),
        spaceBefore=6,
        spaceAfter=4,
    )
    normal = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=f"Receipt {payment.receipt_no}",
        author=identity["name"],
    )
    story = []

    story.append(Paragraph(identity["name"], title))
    contact_line = (
        f"{identity['address']} &nbsp;|&nbsp; {identity['contact']} "
        f"&nbsp;|&nbsp; {identity['email']}"
    )
    story.append(Paragraph(contact_line, subtitle))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#d1d5db")))
    story.append(Spacer(1, 8))
    story.append(Paragraph("PAYMENT RECEIPT", h2))

    meta = [
        [
            "Receipt No.",
            payment.receipt_no,
            "Payment date",
            _as_datetime(payment.paid_at).strftime("%d %b %Y, %H:%M"),
        ],
        [
            "Payment ref.",
            payment.reference,
            "Payment method",
            PAYMENT_METHOD_LABELS.get(payment.method, payment.method.title()),
        ],
    ]
    meta_table = Table(meta, colWidths=[28 * mm, 58 * mm, 30 * mm, 52 * mm])
    meta_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#6b7280")),
                ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#6b7280")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 8))

    story.append(Paragraph("Billed to", h2))
    details = [
        ["Student name", student.full_name if student else "—"],
        ["Roll number", student.roll_number if student else "—"],
        ["Contact", (student.phone if student else "") or "—"],
        ["Email", (student.email if student else "") or "—"],
        ["Room", f"{room_number} ({room_label})"],
        ["Billing period", fee.period_label if fee else "—"],
    ]
    details_table = Table(details, colWidths=[38 * mm, 130 * mm])
    details_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#6b7280")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(details_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Charges", h2))
    charge_rows = [
        ["Description", f"Amount ({currency})"],
        ["Accommodation", _fmt(fee.accommodation_amount)],
        ["Mess", _fmt(fee.mess_amount)],
        ["Laundry", _fmt(fee.laundry_amount)],
        ["Maintenance", _fmt(fee.maintenance_amount)],
    ]
    if to_decimal(fee.other_amount) > 0:
        charge_rows.append(["Other charges", _fmt(fee.other_amount)])
    if to_decimal(fee.discount_amount) > 0:
        charge_rows.append(["Discount", f"-{_fmt(fee.discount_amount)}"])
    if to_decimal(fee.late_fee_amount) > 0:
        charge_rows.append(["Late fee", _fmt(fee.late_fee_amount)])
    charge_rows.append(["Total billed", _fmt(fee.total_amount)])

    charge_table = Table(charge_rows, colWidths=[124 * mm, 44 * mm])
    charge_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2d3d")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#e5e7eb")),
                ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.HexColor("#1f2d3d")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(charge_table)
    story.append(Spacer(1, 10))

    summary = [
        ["Previous outstanding balance", f"{currency}{_fmt(previous_balance)}"],
        ["Amount paid", f"{currency}{_fmt(paid_amount)}"],
        ["Remaining balance", f"{currency}{_fmt(balance_after)}"],
        [
            "Payment status",
            "PAID"
            if balance_after <= 0
            else ("PARTIALLY PAID" if to_decimal(fee.amount_paid) > 0 else "PENDING"),
        ],
    ]
    summary_table = Table(summary, colWidths=[124 * mm, 44 * mm])
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#ecfdf5")),
                ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#065f46")),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 14))

    issuer = payment.recorded_by.email if payment.recorded_by else "System"
    story.append(
        Paragraph(
            f"Issued by: {issuer} &nbsp;&nbsp;•&nbsp;&nbsp; Generated on "
            f"{datetime.now(UTC).strftime('%d %b %Y %H:%M UTC')}",
            normal,
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            "This is a computer-generated receipt. Please retain it for your records.",
            ParagraphStyle(
                "foot",
                parent=normal,
                fontSize=8,
                textColor=colors.HexColor("#9ca3af"),
            ),
        )
    )

    doc.build(story)
    return buffer.getvalue()
