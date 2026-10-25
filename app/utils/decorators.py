"""Authorization decorators and request helpers."""

from __future__ import annotations

from functools import wraps
from urllib.parse import urljoin, urlparse

from flask import abort, flash, redirect, request, url_for
from flask_login import current_user, login_required

from app.constants import ROLE_ADMIN, ROLE_STUDENT


def role_required(*roles: str):
    """Allow the view only for authenticated users having one of ``roles``."""

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(*args, **kwargs):
            if getattr(current_user, "role", None) not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapper

    return decorator


admin_required = role_required(ROLE_ADMIN)
student_required = role_required(ROLE_STUDENT)


def is_safe_url(target: str | None) -> bool:
    """Return True when ``target`` is a relative URL on this host."""
    if not target:
        return False
    host_url = urlparse(request.host_url)
    redirect_url = urlparse(urljoin(request.host_url, target))
    return redirect_url.scheme in ("http", "https") and host_url.netloc == redirect_url.netloc


def redirect_back(fallback_endpoint: str = "admin.dashboard", **values):
    """Redirect to a validated ``next`` parameter, else to ``fallback_endpoint``."""
    target = request.args.get("next") or request.form.get("next")
    if target and is_safe_url(target):
        return redirect(target)
    return redirect(url_for(fallback_endpoint, **values))


def flash_form_errors(form) -> None:
    """Push every WTForms error into the flash queue."""
    for field_name, errors in form.errors.items():
        label = getattr(form, field_name).label.text
        for error in errors:
            flash(f"{label}: {error}", "danger")
