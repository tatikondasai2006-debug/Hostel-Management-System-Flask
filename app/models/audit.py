"""Audit log model."""

from __future__ import annotations

from sqlalchemy import func

from app.extensions import db
from app.models.base import ReprMixin


class AuditLog(ReprMixin, db.Model):
    """An append-only record of important administrative actions.

    Passwords, session tokens and other secrets are never written here.
    """

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_label = db.Column(db.String(150), nullable=True)
    action = db.Column(db.String(60), nullable=False, index=True)
    entity_type = db.Column(db.String(40), nullable=False, index=True)
    entity_id = db.Column(db.String(40), nullable=True)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)

    actor = db.relationship("User", foreign_keys=[actor_user_id])

    __table_args__ = (
        db.Index("ix_audit_entity", "entity_type", "entity_id"),
        db.Index("ix_audit_created", "created_at"),
    )
