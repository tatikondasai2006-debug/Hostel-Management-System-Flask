"""Application configuration objects.

Configuration is environment driven.  The application never hard-codes
secrets or production credentials; everything sensitive is read from
environment variables (see ``.env.example``).
"""

from __future__ import annotations

import os
from datetime import timedelta
from typing import ClassVar

from dotenv import load_dotenv

# Load a local ".env" file if present.  Existing environment variables always
# win, so container/CI provided values are respected.
load_dotenv()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _split_rate(value: str | None, default: str) -> str:
    return (value or default).strip()


class BaseConfig:
    """Settings shared by every environment."""

    # --- Core Flask -------------------------------------------------------
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-secret-key")
    JSON_SORT_KEYS = False

    # --- Database ---------------------------------------------------------
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or os.environ.get(
        "SQLITE_FALLBACK_URL", "sqlite:///hostel_dev.sqlite3"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS: ClassVar[dict] = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "future": True,
    }

    # --- Session / cookies ------------------------------------------------
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _as_bool(os.environ.get("SESSION_COOKIE_SECURE"), False)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = _as_bool(os.environ.get("SESSION_COOKIE_SECURE"), False)
    PERMANENT_SESSION_LIFETIME = timedelta(
        minutes=int(os.environ.get("SESSION_LIFETIME_MINUTES", "120"))
    )

    # --- CSRF / forms -----------------------------------------------------
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # valid for the lifetime of the session

    # --- Rate limiting ----------------------------------------------------
    RATELIMIT_LOGIN = _split_rate(os.environ.get("RATELIMIT_LOGIN"), "10 per minute")
    RATELIMIT_SIGNUP = _split_rate(os.environ.get("RATELIMIT_SIGNUP"), "5 per hour")
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")

    # --- Hostel identity defaults (DB settings override these) -----------
    HOSTEL_NAME = os.environ.get("HOSTEL_NAME", "Sunrise Student Hostel")
    HOSTEL_ADDRESS = os.environ.get("HOSTEL_ADDRESS", "123 Campus Road, Springfield")
    HOSTEL_CONTACT = os.environ.get("HOSTEL_CONTACT", "+1 555 0100")
    HOSTEL_EMAIL = os.environ.get("HOSTEL_EMAIL", "office@hostel.example")
    CURRENCY_SYMBOL = os.environ.get("CURRENCY_SYMBOL", "\u20b9")

    # --- Domain defaults --------------------------------------------------
    DEFAULT_LATE_FEE_PERCENT = os.environ.get("DEFAULT_LATE_FEE_PERCENT", "2.00")
    DEFAULT_LATE_FEE_GRACE_DAYS = int(os.environ.get("LATE_FEE_GRACE_DAYS", "5"))

    # --- Misc -------------------------------------------------------------
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB upload cap
    TRUST_PROXY = _as_bool(os.environ.get("TRUST_PROXY"), False)


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = False
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("TEST_DATABASE_URL") or (
        os.environ.get("SQLITE_FALLBACK_URL", "sqlite:///hostel_test.sqlite3")
    )


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(env: str | None = None):
    """Return the configuration class for ``env`` (defaults to FLASK_ENV)."""
    env = (env or os.environ.get("FLASK_ENV") or "development").lower()
    return CONFIG_MAP.get(env, DevelopmentConfig)
