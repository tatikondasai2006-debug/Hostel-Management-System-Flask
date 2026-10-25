"""Report builders: every report returns ``(headers, rows)`` from the DB."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import select

from app.constants import (
    ALLOCATION_ACTIVE,
    PAYMENT_METHOD_LABELS,
    ROOM_TYPE_LABELS,
    STUDENT_ACTIVE,
)
from app.extensions import db
from app.models import Hostel, Payment, Room, RoomAllocation, Student, StudentFee
from app.utils.money import money


def _student_rows(filters: dict, only_active: bool = False, only_unallocated: bool = False):
    stmt = select(Student)
    if only_active:
        stmt = stmt.where(Student.status == STUDENT_ACTIVE)
    if filters.get("course"):
        stmt = stmt.where(Student.course == filters["course"])
    if filters.get("academic_year"):
        stmt = stmt.where(Student.academic_year == filters["academic_year"])
    if filters.get("status"):
        stmt = stmt.where(Student.status == filters["status"])
    if only_unallocated:
        allocated = select(RoomAllocation.student_id).where(
            RoomAllocation.status == ALLOCATION_ACTIVE
        )
        stmt = stmt.where(Student.id.notin_(allocated))
    stmt = stmt.order_by(Student.roll_number)
    return db.session.execute(stmt).scalars().all()


STUDENT_HEADERS = [
    "Student ID",
    "Roll Number",
    "Full Name",
    "Email",
    "Phone",
    "Course",
    "Academic Year",
    "Status",
    "Room",
    "Hostel",
    "Admission Date",
    "Outstanding",
]


def _student_dict(student: Student) -> dict:
    room = student.current_room
    return {
        "Student ID": student.id,
        "Roll Number": student.roll_number,
        "Full Name": student.full_name,
        "Email": student.email,
        "Phone": student.phone,
        "Course": student.course,
        "Academic Year": student.academic_year,
        "Status": student.status.title(),
        "Room": room.room_number if room else "",
        "Hostel": room.hostel.name if room and room.hostel else "",
        "Admission Date": student.admission_date,
        "Outstanding": f"{money(student.outstanding_balance):.2f}",
    }


def student_register(filters: dict | None = None):
    students = _student_rows(filters or {})
    return STUDENT_HEADERS, [_student_dict(s) for s in students]


def active_students(filters: dict | None = None):
    students = _student_rows(filters or {}, only_active=True)
    return STUDENT_HEADERS, [_student_dict(s) for s in students]


def unallocated_students(filters: dict | None = None):
    students = _student_rows(filters or {}, only_unallocated=True)
    return STUDENT_HEADERS, [_student_dict(s) for s in students]


ROOM_HEADERS = [
    "Room ID",
    "Hostel",
    "Room Number",
    "Floor",
    "Type",
    "Capacity",
    "Occupied",
    "Available",
    "Occupancy %",
    "Status",
    "Monthly Fee",
]


def _room_dict(room: Room) -> dict:
    return {
        "Room ID": room.id,
        "Hostel": room.hostel.name if room.hostel else "",
        "Room Number": room.room_number,
        "Floor": room.floor,
        "Type": ROOM_TYPE_LABELS.get(room.room_type, room.room_type.title()),
        "Capacity": room.capacity,
        "Occupied": room.occupied_beds,
        "Available": max(room.available_beds, 0),
        "Occupancy %": room.occupancy_percent,
        "Status": room.display_status.title(),
        "Monthly Fee": f"{money(room.base_fee):.2f}",
    }


def _room_query(only_available: bool = False):
    stmt = select(Room).join(Hostel, Hostel.id == Room.hostel_id)
    if only_available:
        stmt = stmt.where(Room.status == "available")
    return stmt.order_by(Hostel.name, Room.room_number)


def room_occupancy(filters: dict | None = None):
    rooms = db.session.execute(_room_query()).scalars().all()
    return ROOM_HEADERS, [_room_dict(r) for r in rooms]


def room_availability(filters: dict | None = None):
    rooms = [r for r in db.session.execute(_room_query(True)).scalars().all() if not r.is_full]
    return ROOM_HEADERS, [_room_dict(r) for r in rooms]


ALLOCATION_HEADERS = [
    "Allocation ID",
    "Student",
    "Roll Number",
    "Room",
    "Hostel",
    "Bed",
    "Status",
    "Allocated At",
    "Released At",
    "Reason",
]


def allocation_history(filters: dict | None = None):
    stmt = select(RoomAllocation).order_by(RoomAllocation.allocated_at.desc())
    rows = db.session.execute(stmt).scalars().all()
    data = []
    for a in rows:
        data.append(
            {
                "Allocation ID": a.id,
                "Student": a.student.full_name if a.student else "",
                "Roll Number": a.student.roll_number if a.student else "",
                "Room": a.room.room_number if a.room else "",
                "Hostel": a.room.hostel.name if a.room and a.room.hostel else "",
                "Bed": a.bed_index,
                "Status": a.status.title(),
                "Allocated At": a.allocated_at,
                "Released At": a.released_at or "",
                "Reason": a.release_reason or "",
            }
        )
    return ALLOCATION_HEADERS, data


FEE_HEADERS = [
    "Fee ID",
    "Roll Number",
    "Student",
    "Billing Period",
    "Accommodation",
    "Mess",
    "Laundry",
    "Maintenance",
    "Other",
    "Discount",
    "Late Fee",
    "Total",
    "Paid",
    "Balance",
    "Due Date",
    "Status",
]


def _fee_dict(fee: StudentFee) -> dict:
    return {
        "Fee ID": fee.id,
        "Roll Number": fee.student.roll_number if fee.student else "",
        "Student": fee.student.full_name if fee.student else "",
        "Billing Period": fee.billing_period,
        "Accommodation": f"{money(fee.accommodation_amount):.2f}",
        "Mess": f"{money(fee.mess_amount):.2f}",
        "Laundry": f"{money(fee.laundry_amount):.2f}",
        "Maintenance": f"{money(fee.maintenance_amount):.2f}",
        "Other": f"{money(fee.other_amount):.2f}",
        "Discount": f"{money(fee.discount_amount):.2f}",
        "Late Fee": f"{money(fee.late_fee_amount):.2f}",
        "Total": f"{money(fee.total_amount):.2f}",
        "Paid": f"{money(fee.amount_paid):.2f}",
        "Balance": f"{money(fee.balance):.2f}",
        "Due Date": fee.due_date,
        "Status": fee.status.title(),
    }


def _fee_query():
    return select(StudentFee).join(Student, Student.id == StudentFee.student_id)


def fee_collection(filters: dict | None = None):
    stmt = _fee_query().order_by(StudentFee.billing_period.desc())
    fees = db.session.execute(stmt).scalars().all()
    return FEE_HEADERS, [_fee_dict(f) for f in fees]


def pending_dues(filters: dict | None = None):
    fees = (
        db.session.execute(
            _fee_query()
            .where(StudentFee.amount_paid < StudentFee.total_amount)
            .order_by(StudentFee.due_date)
        )
        .scalars()
        .all()
    )
    return FEE_HEADERS, [_fee_dict(f) for f in fees]


def overdue_payments(filters: dict | None = None):
    fees = (
        db.session.execute(
            _fee_query()
            .where(
                StudentFee.amount_paid < StudentFee.total_amount,
                StudentFee.due_date < date.today(),
            )
            .order_by(StudentFee.due_date)
        )
        .scalars()
        .all()
    )
    return FEE_HEADERS, [_fee_dict(f) for f in fees]


PAYMENT_HEADERS = [
    "Payment ID",
    "Receipt No",
    "Reference",
    "Roll Number",
    "Student",
    "Amount",
    "Method",
    "Status",
    "Paid At",
    "Recorded By",
]


def payment_history(filters: dict | None = None):
    stmt = select(Payment).order_by(Payment.paid_at.desc())
    if filters and filters.get("start_date"):
        start = datetime.combine(filters["start_date"], datetime.min.time(), tzinfo=UTC)
        stmt = stmt.where(Payment.paid_at >= start)
    if filters and filters.get("end_date"):
        end = datetime.combine(filters["end_date"], datetime.max.time(), tzinfo=UTC)
        stmt = stmt.where(Payment.paid_at <= end)
    if filters and filters.get("method"):
        stmt = stmt.where(Payment.method == filters["method"])
    payments = db.session.execute(stmt).scalars().all()
    data = []
    for p in payments:
        data.append(
            {
                "Payment ID": p.id,
                "Receipt No": p.receipt_no,
                "Reference": p.reference,
                "Roll Number": p.student.roll_number if p.student else "",
                "Student": p.student.full_name if p.student else "",
                "Amount": f"{money(p.amount):.2f}",
                "Method": PAYMENT_METHOD_LABELS.get(p.method, p.method),
                "Status": p.status.title(),
                "Paid At": p.paid_at,
                "Recorded By": p.recorded_by.email if p.recorded_by else "System",
            }
        )
    return PAYMENT_HEADERS, data


REPORTS = {
    "student-register": {
        "title": "Complete Student Register",
        "builder": student_register,
        "slug": "student-register",
    },
    "active-students": {
        "title": "Active Students",
        "builder": active_students,
        "slug": "active-students",
    },
    "unallocated-students": {
        "title": "Unallocated Students",
        "builder": unallocated_students,
        "slug": "unallocated-students",
    },
    "room-occupancy": {
        "title": "Room Occupancy",
        "builder": room_occupancy,
        "slug": "room-occupancy",
    },
    "room-availability": {
        "title": "Room Availability",
        "builder": room_availability,
        "slug": "room-availability",
    },
    "allocation-history": {
        "title": "Allocation History",
        "builder": allocation_history,
        "slug": "allocation-history",
    },
    "fee-collection": {
        "title": "Fee Collection",
        "builder": fee_collection,
        "slug": "fee-collection",
    },
    "pending-dues": {
        "title": "Pending Dues",
        "builder": pending_dues,
        "slug": "pending-dues",
    },
    "overdue-payments": {
        "title": "Overdue Payments",
        "builder": overdue_payments,
        "slug": "overdue-payments",
    },
    "payment-history": {
        "title": "Payment Transaction History",
        "builder": payment_history,
        "slug": "payment-history",
    },
}


def build_report(slug: str, filters: dict | None = None):
    report = REPORTS.get(slug)
    if report is None:
        raise KeyError(slug)
    headers, rows = report["builder"](filters or {})
    return {"title": report["title"], "slug": slug, "headers": headers, "rows": rows}
