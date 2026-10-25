"""Small pagination helper shared by list views."""

from __future__ import annotations

from flask import request


def page_args(default_per_page: int = 15) -> tuple[int, int]:
    """Return a validated ``(page, per_page)`` tuple from the query string."""
    try:
        page = int(request.args.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    page = max(page, 1)
    try:
        per_page = int(request.args.get("per_page", default_per_page))
    except (TypeError, ValueError):
        per_page = default_per_page
    per_page = min(max(per_page, 5), 100)
    return page, per_page


def query_string_without_page() -> dict:
    args = request.args.to_dict(flat=True)
    args.pop("page", None)
    return args
