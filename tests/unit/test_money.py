"""Unit tests for decimal-safe money helpers."""

from decimal import Decimal

from app.utils.money import format_currency, money, to_decimal


def test_to_decimal_none_is_zero():
    assert to_decimal(None) == Decimal("0.00")


def test_to_decimal_empty_string_is_zero():
    assert to_decimal("") == Decimal("0.00")


def test_to_decimal_invalid_is_zero():
    assert to_decimal("not-a-number") == Decimal("0.00")


def test_to_decimal_passes_decimal_through():
    value = Decimal("12.34")
    assert to_decimal(value) is value


def test_to_decimal_parses_string():
    assert to_decimal("19.95") == Decimal("19.95")


def test_money_rounds_half_up():
    assert money("1.005") == Decimal("1.01")


def test_money_half_up_not_bankers():
    # Python's round() would give 2.67 (banker's rounding) here.
    assert money("2.675") == Decimal("2.68")


def test_money_quantises_to_two_places():
    assert money(Decimal("10")) == Decimal("10.00")
    assert str(money(5)) == "5.00"


def test_format_currency_with_symbol():
    assert format_currency(1234.5, "$") == "$1,234.50"


def test_format_currency_without_symbol():
    assert format_currency("0") == "0.00"
    assert format_currency(None) == "0.00"
