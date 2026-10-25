"""Reusable model mixins."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    """Timezone-aware UTC now (used for Python-side defaults)."""
    return datetime.now(UTC)


class TimestampMixin:
    """Adds ``created_at`` / ``updated_at`` columns maintained by the DB."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ReprMixin:
    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        pk = getattr(self, "id", None)
        return f"<{self.__class__.__name__} id={pk}>"
