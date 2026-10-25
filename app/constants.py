"""Shared domain constants (enumerated string values).

Plain string values + CHECK constraints are used instead of native PostgreSQL
enums: this keeps migrations simple while still enforcing values at the
database level.
"""

from __future__ import annotations

# --- Roles -----------------------------------------------------------------
ROLE_ADMIN = "admin"
ROLE_STUDENT = "student"
ROLES = (ROLE_ADMIN, ROLE_STUDENT)

# --- Student status --------------------------------------------------------
STUDENT_ACTIVE = "active"
STUDENT_INACTIVE = "inactive"
STUDENT_ARCHIVED = "archived"
STUDENT_STATUSES = (STUDENT_ACTIVE, STUDENT_INACTIVE, STUDENT_ARCHIVED)

# --- Fee status (derived cache) -------------------------------------------
FEE_NONE = "none"
FEE_PENDING = "pending"
FEE_PARTIAL = "partial"
FEE_PAID = "paid"
FEE_OVERDUE = "overdue"
FEE_STATUSES = (FEE_NONE, FEE_PENDING, FEE_PARTIAL, FEE_PAID, FEE_OVERDUE)

# --- Room ------------------------------------------------------------------
ROOM_SINGLE = "single"
ROOM_DOUBLE = "double"
ROOM_DORMITORY = "dormitory"
ROOM_TYPES = (ROOM_SINGLE, ROOM_DOUBLE, ROOM_DORMITORY)
ROOM_TYPE_LABELS = {
    ROOM_SINGLE: "Single",
    ROOM_DOUBLE: "Double",
    ROOM_DORMITORY: "Dormitory",
}

ROOM_AVAILABLE = "available"
ROOM_MAINTENANCE = "maintenance"
ROOM_UNAVAILABLE = "unavailable"
ROOM_STATUSES = (ROOM_AVAILABLE, ROOM_MAINTENANCE, ROOM_UNAVAILABLE)

# derived (never stored) occupancy states used for filtering / display
ROOM_FULL = "full"
ROOM_PARTIAL = "partial"

# --- Allocation ------------------------------------------------------------
ALLOCATION_ACTIVE = "active"
ALLOCATION_RELEASED = "released"
ALLOCATION_STATUSES = (ALLOCATION_ACTIVE, ALLOCATION_RELEASED)

RELEASE_TRANSFER = "transfer"
RELEASE_CHECKOUT = "checkout"
RELEASE_DEACTIVATION = "deactivation"
RELEASE_ADMIN = "admin"

# --- Payments --------------------------------------------------------------
PAYMENT_CASH = "cash"
PAYMENT_CARD = "card"
PAYMENT_BANK_TRANSFER = "bank_transfer"
PAYMENT_UPI = "upi"
PAYMENT_CHEQUE = "cheque"
PAYMENT_METHODS = (
    PAYMENT_CASH,
    PAYMENT_CARD,
    PAYMENT_BANK_TRANSFER,
    PAYMENT_UPI,
    PAYMENT_CHEQUE,
)
PAYMENT_METHOD_LABELS = {
    PAYMENT_CASH: "Cash",
    PAYMENT_CARD: "Card",
    PAYMENT_BANK_TRANSFER: "Bank transfer",
    PAYMENT_UPI: "UPI",
    PAYMENT_CHEQUE: "Cheque",
}

PAYMENT_COMPLETED = "completed"
PAYMENT_REVERSED = "reversed"
PAYMENT_STATUSES = (PAYMENT_COMPLETED, PAYMENT_REVERSED)

# --- Settings keys ---------------------------------------------------------
SETTING_HOSTEL_NAME = "hostel_name"
SETTING_HOSTEL_ADDRESS = "hostel_address"
SETTING_HOSTEL_CONTACT = "hostel_contact"
SETTING_HOSTEL_EMAIL = "hostel_email"
SETTING_CURRENCY_SYMBOL = "currency_symbol"
SETTING_LATE_FEE_PERCENT = "late_fee_percent"
SETTING_LATE_FEE_GRACE_DAYS = "late_fee_grace_days"

DEFAULT_SETTINGS = {
    SETTING_HOSTEL_NAME: "Sunrise Student Hostel",
    SETTING_HOSTEL_ADDRESS: "123 Campus Road, Springfield",
    SETTING_HOSTEL_CONTACT: "+1 555 0100",
    SETTING_HOSTEL_EMAIL: "office@sunrise-hostel.example",
    SETTING_CURRENCY_SYMBOL: "\u20b9",
    SETTING_LATE_FEE_PERCENT: "2.00",
    SETTING_LATE_FEE_GRACE_DAYS: "5",
}
