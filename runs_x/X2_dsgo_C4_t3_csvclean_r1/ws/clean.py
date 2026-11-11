"""Clean a messy order export CSV.

Usage:
    python3 clean.py INPUT.csv OUTPUT.csv

The script reads ``INPUT.csv``, normalises every field according to the
export rules, removes duplicate and invalid rows, and writes ``OUTPUT.csv``.
Only the Python standard library is used.
"""

from __future__ import annotations

import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from typing import Dict, List, Optional, Tuple

INPUT_COLUMNS = (
    "order_id",
    "customer_email",
    "amount",
    "currency",
    "order_date",
    "status",
    "updated_at",
)

OUTPUT_COLUMNS = (
    "order_id",
    "customer_email",
    "amount",
    "currency",
    "order_date",
    "status",
)

ALLOWED_STATUSES = frozenset(
    {"pending", "paid", "shipped", "cancelled", "refunded"}
)

CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

_NUMERIC_DASH = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_NUMERIC_YEAR_SLASH = re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})$")
_NUMERIC_DAY_FIRST = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")
_NUMERIC_MONTH_FIRST = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_MONTH_FIRST = re.compile(r"^([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})$")
_DAY_FIRST = re.compile(r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$")

_UPDATED_AT = re.compile(
    r"^(\d{4})-(\d{1,2})-(\d{1,2})[T ]"
    r"(\d{1,2}):(\d{1,2}):(\d{1,2})Z?$"
)

_DECIMAL_NUMBER = re.compile(r"^\d+(?:\.\d+)?$")

OutputRow = Tuple[str, str, str, str, str, str]
Record = Tuple[str, datetime, OutputRow]


def normalise_header(name: str) -> str:
    """Return a header name trimmed, lowercased, with spaces as underscores."""
    return re.sub(r"\s+", "_", name.strip().lower())


def parse_amount(raw: str) -> Optional[Decimal]:
    """Parse an exported amount and return the rounded Decimal value.

    Returns ``None`` when the value is empty or cannot be interpreted.

    Args:
        raw: The raw amount cell.

    Returns:
        The amount rounded to two decimal places, or ``None``.
    """
    text = raw.strip()
    if not text:
        return None

    for symbol in CURRENCY_SYMBOLS:
        text = text.replace(symbol, "")
    text = re.sub(r"\s+", "", text)

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]

    if not text:
        return None

    has_dot = "." in text
    has_comma = "," in text

    if has_dot and has_comma:
        if text.rfind(".") > text.rfind(","):
            decimal_sep = "."
            thousands_sep = ","
        else:
            decimal_sep = ","
            thousands_sep = "."
        if text.count(decimal_sep) != 1:
            return None
        head, tail = text.split(decimal_sep)
        head = head.replace(thousands_sep, "")
        normalised = head + "." + tail
    elif has_comma:
        last_comma = text.rfind(",")
        tail = text[last_comma + 1 :]
        if len(tail) == 2 and tail.isdigit():
            head = text[:last_comma].replace(",", "")
            normalised = head + "." + tail
        else:
            normalised = text.replace(",", "")
    elif has_dot:
        if text.count(".") != 1:
            return None
        normalised = text
    else:
        normalised = text

    if not _DECIMAL_NUMBER.match(normalised):
        return None

    try:
        with localcontext() as context:
            context.prec = 100
            value = Decimal(normalised)
            if negative:
                value = -value
            rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None

    if rounded.is_zero():
        rounded = abs(rounded)
    return rounded


def amount_currency(raw: str) -> Optional[str]:
    """Return the currency implied by a symbol in the raw amount, if any."""
    for character in raw:
        if character in CURRENCY_SYMBOLS:
            return CURRENCY_SYMBOLS[character]
    return None


def normalise_currency(raw: str) -> str:
    """Return the trimmed, uppercased currency, mapping known symbols."""
    text = raw.strip().upper()
    if text in CURRENCY_SYMBOLS:
        return CURRENCY_SYMBOLS[text]
    return text


def normalise_email(raw: str) -> str:
    """Return the trimmed, lowercased email if it is well formed, else empty."""
    email = raw.strip().lower()
    if email.count("@") != 1:
        return ""
    local_part, domain = email.split("@")
    if not local_part or not domain:
        return ""
    return email


def _build_date(year: int, month: int, day: int) -> Optional[date]:
    """Build a date, returning ``None`` when the values are invalid."""
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_date(raw: str) -> Optional[date]:
    """Parse one of the accepted export date formats.

    Args:
        raw: The raw order date cell.

    Returns:
        The parsed date, or ``None`` when the value is missing or invalid.
    """
    text = raw.strip()
    if not text:
        return None

    match = _NUMERIC_DASH.match(text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return _build_date(year, month, day)

    match = _NUMERIC_YEAR_SLASH.match(text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return _build_date(year, month, day)

    match = _NUMERIC_DAY_FIRST.match(text)
    if match:
        day, month, year = (int(part) for part in match.groups())
        return _build_date(year, month, day)

    match = _NUMERIC_MONTH_FIRST.match(text)
    if match:
        month, day, year = (int(part) for part in match.groups())
        return _build_date(year, month, day)

    match = _MONTH_FIRST.match(text)
    if match:
        month_name, day, year = match.groups()
        month = MONTHS.get(month_name.lower())
        if month is None:
            return None
        return _build_date(int(year), month, int(day))

    match = _DAY_FIRST.match(text)
    if match:
        day, month_name, year = match.groups()
        month = MONTHS.get(month_name.lower())
        if month is None:
            return None
        return _build_date(int(year), month, int(day))

    return None


def parse_updated_at(raw: str) -> datetime:
    """Parse the update timestamp, using the oldest possible value when invalid."""
    text = raw.strip()
    if not text:
        return datetime.min

    match = _UPDATED_AT.match(text)
    if not match:
        return datetime.min

    year, month, day, hour, minute, second = (int(part) for part in match.groups())
    try:
        return datetime(year, month, day, hour, minute, second)
    except ValueError:
        return datetime.min


def normalise_status(raw: str) -> str:
    """Return the normalised order status, or ``unknown``."""
    status = raw.strip().lower()
    if status == "canceled":
        status = "cancelled"
    if status in ALLOWED_STATUSES:
        return status
    return "unknown"


def format_amount(value: Decimal) -> str:
    """Format a Decimal amount with exactly two decimal places."""
    return format(value, "f")


def read_records(path: str) -> List[Record]:
    """Read valid, normalised records from the input CSV.

    Args:
        path: Path to the input CSV.

    Returns:
        A list of ``(order_id, updated_at, output_row)`` tuples. Invalid rows
        and rows without an id, amount, or date are omitted.
    """
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        raw_lines = handle.read().splitlines()

    lines = [
        line
        for line in raw_lines
        if line.strip() and not line.startswith("#")
    ]
    reader = csv.reader(lines)
    try:
        header = next(reader)
    except StopIteration:
        return []

    indexes: Dict[str, int] = {}
    for position, name in enumerate(header):
        key = normalise_header(name)
        if key in INPUT_COLUMNS and key not in indexes:
            indexes[key] = position

    def cell(row: List[str], column: str) -> str:
        position = indexes.get(column)
        if position is None or position >= len(row):
            return ""
        return row[position]

    records: List[Record] = []
    for row in reader:
        order_id = cell(row, "order_id").strip().upper()
        if not order_id:
            continue

        raw_amount = cell(row, "amount")
        amount = parse_amount(raw_amount)
        if amount is None:
            continue

        order_date = parse_date(cell(row, "order_date"))
        if order_date is None:
            continue

        email = normalise_email(cell(row, "customer_email"))
        currency = normalise_currency(cell(row, "currency"))
        if not currency:
            currency = amount_currency(raw_amount) or "USD"
        status = normalise_status(cell(row, "status"))
        updated_at = parse_updated_at(cell(row, "updated_at"))

        cleaned: OutputRow = (
            order_id,
            email,
            format_amount(amount),
            currency,
            order_date.isoformat(),
            status,
        )
        records.append((order_id, updated_at, cleaned))

    return records


def deduplicate(records: List[Record]) -> List[OutputRow]:
    """Keep the latest updated row for each order id, later rows winning ties."""
    best: Dict[str, Tuple[datetime, OutputRow]] = {}
    for order_id, updated_at, row in records:
        current = best.get(order_id)
        if current is None or updated_at >= current[0]:
            best[order_id] = (updated_at, row)
    return [entry[1] for entry in best.values()]


def write_output(path: str, rows: List[OutputRow]) -> None:
    """Write the cleaned rows sorted by order date and order id."""
    rows.sort(key=lambda row: (row[4], row[0]))
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(OUTPUT_COLUMNS)
        writer.writerows(rows)


def main(argv: List[str]) -> int:
    """Run the converter with command-line arguments."""
    if len(argv) != 3:
        print("usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2

    records = read_records(argv[1])
    rows = deduplicate(records)
    write_output(argv[2], rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
