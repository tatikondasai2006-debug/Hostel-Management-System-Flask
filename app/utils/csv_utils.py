"""CSV export helpers with spreadsheet-formula-injection protection."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from decimal import Decimal

from flask import Response

# Characters that make Excel / LibreOffice treat a cell as a formula.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


def sanitize_csv_value(value) -> str:
    """Neutralise CSV formula injection without mangling real numbers.

    Non-string values (ints, Decimals, dates, ...) are converted normally so
    that negative numbers are preserved.  Strings beginning with a formula
    trigger are prefixed with a single quote, which spreadsheets display as
    text and never execute.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    text = str(value)
    if text and text[0] in _FORMULA_PREFIXES:
        return "'" + text
    return text


def rows_to_csv(rows, headers) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow([sanitize_csv_value(h) for h in headers])
    for row in rows:
        if hasattr(row, "keys"):
            writer.writerow([sanitize_csv_value(row[h]) for h in headers])
        else:
            writer.writerow([sanitize_csv_value(v) for v in row])
    return buffer.getvalue()


def csv_response(rows, headers, filename: str) -> Response:
    """Build a downloadable ``text/csv`` response."""
    payload = rows_to_csv(rows, headers)
    # Prepend a UTF-8 BOM so Excel detects the encoding correctly.
    body = "\ufeff" + payload
    response = Response(body, mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


def safe_filename(prefix: str, suffix: str = "") -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    cleaned = "".join(c for c in prefix if c.isalnum() or c in "-_") or "export"
    tail = f"-{suffix}" if suffix else ""
    return f"{cleaned}{tail}-{stamp}.csv"
