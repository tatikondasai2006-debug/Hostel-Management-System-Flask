"""Runtime application settings (key/value)."""

from __future__ import annotations

from app.extensions import db
from app.models.base import ReprMixin, TimestampMixin


class Setting(TimestampMixin, ReprMixin, db.Model):
    """A mutable, administrator-managed configuration value."""

    __tablename__ = "app_settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(60), unique=True, nullable=False, index=True)
    value = db.Column(db.Text)
