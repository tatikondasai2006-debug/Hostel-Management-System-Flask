"""Unit tests for CSV export helpers (formula-injection protection)."""

from datetime import date, datetime
from decimal import Decimal

from app.utils.csv_utils import rows_to_csv, safe_filename, sanitize_csv_value


def test_equals_prefix_is_neutralised():
    assert sanitize_csv_value("=1+1") == "'=1+1"


def test_plus_prefix_is_neutralised():
    assert sanitize_csv_value("+cmd") == "'+cmd"


def test_at_prefix_is_neutralised():
    assert sanitize_csv_value("@SUM(A1)") == "'@SUM(A1)"


def test_negative_number_is_preserved():
    assert sanitize_csv_value(-5) == "-5"
    assert sanitize_csv_value(Decimal("-1.50")) == "-1.50"


def test_none_becomes_empty_string():
    assert sanitize_csv_value(None) == ""


def test_booleans_are_lowercase():
    assert sanitize_csv_value(True) == "true"
    assert sanitize_csv_value(False) == "false"


def test_dates_use_isoformat():
    assert sanitize_csv_value(date(2026, 1, 2)) == "2026-01-02"
    assert sanitize_csv_value(datetime(2026, 1, 2, 3, 4, 5)) == "2026-01-02T03:04:05"


def test_plain_text_is_unchanged():
    assert sanitize_csv_value("Springfield") == "Springfield"


def test_rows_to_csv_renders_header_and_row():
    output = rows_to_csv([{"A": "=bad", "B": 1}], ["A", "B"])
    lines = output.strip().split("\r\n")
    assert lines[0] == "A,B"
    assert lines[1] == "'=bad,1"


def test_rows_to_csv_accepts_sequences():
    output = rows_to_csv([[1, "x"]], ["A", "B"])
    lines = output.strip().split("\r\n")
    assert lines[1] == "1,x"


def test_safe_filename_contains_slug_and_ext():
    name = safe_filename("hostel", "student-register")
    assert "student-register" in name
    assert name.endswith(".csv")
