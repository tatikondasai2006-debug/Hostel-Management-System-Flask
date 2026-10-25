"""Dashboard aggregation service (all figures come from the database)."""

from __future__ import annotations

from collections import OrderedDict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.constants import (
    ALLOCATION_ACTIVE,
    ROOM_AVAILABLE,
    ROOM_TYPE_LABELS,
    ROOM_TYPES,
    STUDENT_ACTIVE,
)
from app.extensions import db
from app.models import (
    Hostel,
    Payment,
    Room,
    RoomAllocation,
    Student,
    StudentFee,
)
from app.utils.money import money


def _money_sum(stmt) -> Decimal:
    return money(db.session.execute(stmt).scalar_one() or 0)


def admin_dashboard_stats() -> dict:
    """Return every metric rendered on the administrator dashboard."""
    total_students = db.session.execute(select(func.count()).select_from(Student)).scalar_one()
    active_students = db.session.execute(
        select(func.count()).select_from(Student).where(Student.status == STUDENT_ACTIVE)
    ).scalar_one()

    total_rooms = db.session.execute(select(func.count()).select_from(Room)).scalar_one()
    total_capacity = int(
        db.session.execute(select(func.coalesce(func.sum(Room.capacity), 0))).scalar_one() or 0
    )
    occupied_beds = int(
        db.session.execute(
            select(func.count())
            .select_from(RoomAllocation)
            .where(RoomAllocation.status == ALLOCATION_ACTIVE)
        ).scalar_one()
        or 0
    )
    available_beds = max(total_capacity - occupied_beds, 0)
    occupancy_percent = round(occupied_beds / total_capacity * 100, 1) if total_capacity else 0.0

    start_of_month = date.today().replace(day=1)
    month_start_dt = datetime(start_of_month.year, start_of_month.month, 1, tzinfo=UTC)
    monthly_collection = _money_sum(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.paid_at >= month_start_dt, Payment.status == "completed"
        )
    )

    total_outstanding = _money_sum(
        select(func.coalesce(func.sum(StudentFee.total_amount - StudentFee.amount_paid), 0))
    )
    overdue_records = db.session.execute(
        select(func.count())
        .select_from(StudentFee)
        .where(
            StudentFee.amount_paid < StudentFee.total_amount,
            StudentFee.due_date < date.today(),
        )
    ).scalar_one()

    recent_payments = (
        db.session.execute(select(Payment).order_by(Payment.paid_at.desc()).limit(6))
        .scalars()
        .all()
    )
    recent_allocations = (
        db.session.execute(
            select(RoomAllocation).order_by(RoomAllocation.allocated_at.desc()).limit(6)
        )
        .scalars()
        .all()
    )

    total_paid = _money_sum(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "completed")
    )

    return {
        "total_students": total_students,
        "active_students": active_students,
        "inactive_students": total_students - active_students,
        "total_rooms": total_rooms,
        "total_capacity": total_capacity,
        "occupied_beds": occupied_beds,
        "available_beds": available_beds,
        "occupancy_percent": occupancy_percent,
        "monthly_collection": monthly_collection,
        "total_outstanding": total_outstanding,
        "total_collected": total_paid,
        "overdue_records": overdue_records,
        "recent_payments": recent_payments,
        "recent_allocations": recent_allocations,
    }


def occupancy_by_room_type() -> list[dict]:
    """Capacity vs occupancy per room type (chart data)."""
    capacity_rows = dict(
        db.session.execute(
            select(Room.room_type, func.coalesce(func.sum(Room.capacity), 0)).group_by(
                Room.room_type
            )
        ).all()
    )
    occupied_rows = dict(
        db.session.execute(
            select(Room.room_type, func.count())
            .select_from(RoomAllocation)
            .join(Room, Room.id == RoomAllocation.room_id)
            .where(RoomAllocation.status == ALLOCATION_ACTIVE)
            .group_by(Room.room_type)
        ).all()
    )
    data = []
    for room_type in ROOM_TYPES:
        capacity = int(capacity_rows.get(room_type, 0) or 0)
        occupied = int(occupied_rows.get(room_type, 0) or 0)
        data.append(
            {
                "label": ROOM_TYPE_LABELS.get(room_type, room_type.title()),
                "capacity": capacity,
                "occupied": occupied,
                "available": max(capacity - occupied, 0),
                "occupancy_percent": round(occupied / capacity * 100, 1) if capacity else 0.0,
            }
        )
    return data


def occupancy_by_hostel() -> list[dict]:
    rows = db.session.execute(
        select(
            Hostel.name,
            func.coalesce(func.sum(Room.capacity), 0),
        )
        .select_from(Hostel)
        .outerjoin(Room, Room.hostel_id == Hostel.id)
        .group_by(Hostel.name)
        .order_by(Hostel.name)
    ).all()
    occupied = dict(
        db.session.execute(
            select(Room.hostel_id, func.count())
            .select_from(RoomAllocation)
            .join(Room, Room.id == RoomAllocation.room_id)
            .where(RoomAllocation.status == ALLOCATION_ACTIVE)
            .group_by(Room.hostel_id)
        ).all()
    )
    hostel_ids = dict(db.session.execute(select(Hostel.name, Hostel.id)).all())
    data = []
    for name, capacity in rows:
        capacity = int(capacity or 0)
        hid = hostel_ids.get(name)
        occ = int(occupied.get(hid, 0) or 0)
        data.append(
            {
                "label": name,
                "capacity": capacity,
                "occupied": occ,
                "occupancy_percent": round(occ / capacity * 100, 1) if capacity else 0.0,
            }
        )
    return data


def _month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def monthly_payment_trend(months: int = 6) -> dict:
    """Fee collection per month for the last ``months`` months."""
    today = date.today()
    first = (today.replace(day=1) - timedelta(days=31 * (months - 1))).replace(day=1)

    buckets: OrderedDict[str, Decimal] = OrderedDict()
    cursor = first
    while cursor <= today.replace(day=1):
        buckets[cursor.strftime("%Y-%m")] = Decimal("0.00")
        year = cursor.year + (1 if cursor.month == 12 else 0)
        month = 1 if cursor.month == 12 else cursor.month + 1
        cursor = date(year, month, 1)

    start_dt = datetime(first.year, first.month, 1, tzinfo=UTC)
    payments = db.session.execute(
        select(Payment.paid_at, Payment.amount).where(
            Payment.paid_at >= start_dt, Payment.status == "completed"
        )
    ).all()
    for paid_at, amount in payments:
        key = _month_key(paid_at)
        if key in buckets:
            buckets[key] += money(amount)

    labels = [datetime.strptime(k, "%Y-%m").strftime("%b %Y") for k in buckets]
    return {"labels": labels, "values": [float(v) for v in buckets.values()]}


def paid_vs_pending() -> dict:
    total_paid = _money_sum(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "completed")
    )
    total_outstanding = _money_sum(
        select(func.coalesce(func.sum(StudentFee.total_amount - StudentFee.amount_paid), 0))
    )
    return {"paid": float(total_paid), "pending": float(total_outstanding)}


def availability_summary() -> dict:
    total = db.session.execute(select(func.count()).select_from(Room)).scalar_one()
    available = db.session.execute(
        select(func.count()).select_from(Room).where(Room.status == ROOM_AVAILABLE)
    ).scalar_one()
    return {"total": total, "available": available}
