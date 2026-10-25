"""Runtime settings service (DB-backed, with per-request caching)."""

from __future__ import annotations

from decimal import Decimal

from flask import current_app, g

from app.constants import (
    DEFAULT_SETTINGS,
    SETTING_CURRENCY_SYMBOL,
    SETTING_HOSTEL_ADDRESS,
    SETTING_HOSTEL_CONTACT,
    SETTING_HOSTEL_EMAIL,
    SETTING_HOSTEL_NAME,
    SETTING_LATE_FEE_GRACE_DAYS,
    SETTING_LATE_FEE_PERCENT,
)
from app.extensions import db
from app.models import Setting
from app.utils.money import to_decimal


def _cache() -> dict:
    if not hasattr(g, "_settings_cache"):
        g._settings_cache = {}
    return g._settings_cache


def _config_default(key: str) -> str:
    config_map = {
        SETTING_HOSTEL_NAME: "HOSTEL_NAME",
        SETTING_HOSTEL_ADDRESS: "HOSTEL_ADDRESS",
        SETTING_HOSTEL_CONTACT: "HOSTEL_CONTACT",
        SETTING_HOSTEL_EMAIL: "HOSTEL_EMAIL",
        SETTING_CURRENCY_SYMBOL: "CURRENCY_SYMBOL",
        SETTING_LATE_FEE_PERCENT: "DEFAULT_LATE_FEE_PERCENT",
        SETTING_LATE_FEE_GRACE_DAYS: "DEFAULT_LATE_FEE_GRACE_DAYS",
    }
    return str(current_app.config.get(config_map.get(key, ""), DEFAULT_SETTINGS.get(key, "")))


def get_setting(key: str, default: str | None = None) -> str:
    cache = _cache()
    if key in cache:
        return cache[key]
    row = db.session.execute(db.select(Setting).where(Setting.key == key)).scalar_one_or_none()
    if row is not None and row.value is not None:
        value = row.value
    elif default is not None:
        value = default
    else:
        value = _config_default(key)
    cache[key] = value
    return value


def set_setting(key: str, value) -> Setting:
    row = db.session.execute(db.select(Setting).where(Setting.key == key)).scalar_one_or_none()
    if row is None:
        row = Setting(key=key, value=str(value))
        db.session.add(row)
    else:
        row.value = str(value)
    _cache()[key] = str(value)
    return row


def clear_cache() -> None:
    if hasattr(g, "_settings_cache"):
        g._settings_cache = {}


def get_hostel_identity() -> dict:
    return {
        "name": get_setting(SETTING_HOSTEL_NAME),
        "address": get_setting(SETTING_HOSTEL_ADDRESS),
        "contact": get_setting(SETTING_HOSTEL_CONTACT),
        "email": get_setting(SETTING_HOSTEL_EMAIL),
    }


def get_currency_symbol() -> str:
    return get_setting(SETTING_CURRENCY_SYMBOL)


def get_late_fee_policy() -> tuple[Decimal, int]:
    percent = to_decimal(get_setting(SETTING_LATE_FEE_PERCENT))
    try:
        grace = int(float(get_setting(SETTING_LATE_FEE_GRACE_DAYS)))
    except (TypeError, ValueError):
        grace = 5
    return percent, grace
