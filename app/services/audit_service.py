"""Audit logging service.

Audit rows are added to the *current* session so that they participate in the
same transaction as the action they describe (atomic with the change), but the
helper never commits on its own.  Callers decide the transaction boundary.
"""

from __future__ import annotations

import json

from flask import has_request_context, request
from flask_login import current_user

from app.extensions import db
from app.models import AuditLog


def _actor():
    if getattr(current_user, "is_authenticated", False):
        return current_user
    return None


def log_action(
    action: str,
    entity_type: str,
    entity_id=None,
    details: dict | None = None,
    actor=None,
) -> AuditLog:
    """Create an :class:`AuditLog` row in the current session (no commit)."""
    actor = actor or _actor()
    ip = None
    if has_request_context():
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        if ip and "," in ip:
            ip = ip.split(",")[0].strip()

    entry = AuditLog(
        actor_user_id=getattr(actor, "id", None),
        actor_label=getattr(actor, "email", None) or "system",
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        details=json.dumps(details, default=str) if details else None,
        ip_address=ip,
    )
    db.session.add(entry)
    return entry
