"""Decimal-safe money helpers.

Financial values are always handled as :class:`decimal.Decimal`.  Binary
floating point is never used for money.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

TWO_PLACES = Decimal("0.01")


def to_decimal(value, default: Decimal = Decimal("0.00")) -> Decimal:
    """Best-effort conversion of ``value`` to a 2-decimal ``Decimal``."""
    if value is None or value == "":
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def money(value) -> Decimal:
    """Quantise ``value`` to 2 decimals using banker-free ROUND_HALF_UP."""
    return to_decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def format_currency(value, symbol: str = "") -> str:
    amount = money(value)
    text = f"{amount:,.2f}"
    return f"{symbol}{text}" if symbol else text
