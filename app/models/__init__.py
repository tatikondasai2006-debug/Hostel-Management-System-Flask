"""Database models package.

Importing this package registers every model with SQLAlchemy's metadata so
Flask-Migrate can autogenerate migrations.
"""

from app.models.allocation import RoomAllocation
from app.models.audit import AuditLog
from app.models.base import TimestampMixin, utcnow
from app.models.fees import FeeStructure, StudentFee
from app.models.hostel import Hostel
from app.models.payment import Payment, PaymentReversal
from app.models.room import Room
from app.models.settings import Setting
from app.models.student import Student
from app.models.user import User

__all__ = [
    "AuditLog",
    "FeeStructure",
    "Hostel",
    "Payment",
    "PaymentReversal",
    "Room",
    "RoomAllocation",
    "Setting",
    "Student",
    "StudentFee",
    "TimestampMixin",
    "User",
    "utcnow",
]
