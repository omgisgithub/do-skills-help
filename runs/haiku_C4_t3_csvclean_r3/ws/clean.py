"""Clean a messy order export CSV into a normalised CSV.

Usage: python3 clean.py INPUT.csv OUTPUT.csv
"""

from __future__ import annotations

import csv
import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

REQUIRED_COLUMNS = (
    "order_id",
    "customer_email",
    "amount",
    "currency",
    "order_date",
    "status",
    "updated_at",
)
OUTPUT_COLUMNS = ("order_id", "customer_email", "amount", "currency", "order_date", "status")
ALLOWED_STATUSES = frozenset({"pending", "paid", "shipped", "cancelled", "refunded"})
CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
CENT = Decimal("0.01")

_MONTH_NAMES = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)
# Full English month names and their three-letter abbreviations, lowercased.
MONTHS = {alias: number for number, name in enumerate(_MONTH_NAMES, 1) for alias in (name, name[:3])}

_PLAIN_NUMBER = re.compile(r"[0-9]+(\.[0-9]+)?|\.[0-9]+")
_ISO_DATE = re.compile(r"([0-9]{4})([-/])([0-9]{1,2})\2([0-9]{1,2})")
_DAY_FIRST_DOTTED = re.compile(r"([0-9]{1,2})\.([0-9]{1,2})\.([0-9]{4})")
_MONTH_FIRST_SLASHED = re.compile(r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})")
_MONTH_NAME_FIRST = re.compile(r"([a-z]+) ([0-9]{1,2}), ([0-9]{4})")
_DAY_FIRST_MONTH_NAME = re.compile(r"([0-9]{1,2}) ([a-z]+) ([0-9]{4})")
_UPDATED_AT_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass(frozen=True)
class OrderRow:
    """One validated and normalised order row.

    Attributes:
        order_id: Uppercased order identifier.
        customer_email: Lowercased email, or an empty string if it is not usable.
        amount: Signed amount rounded to two decimals.
        currency: Three-letter currency code.
        order_date: Calendar date of the order.
        status: One of ``ALLOWED_STATUSES`` or ``unknown``.
        updated_at: Naive timestamp used only for de-duplication.
    """

    order_id: str
    customer_email: str
    amount: Decimal
    currency: str
    order_date: date
    status: str
    updated_at: datetime


def load_records(path: Path) -> list[dict[str, str]]:
    """Read the CSV, skipping blank and ``#`` comment lines, and key rows by column name.

    Args:
        path: The raw export to read. A leading UTF-8 BOM is removed.

    Returns:
        One dict per data row, holding every required column with stripped values.

    Raises:
        ValueError: If a required column is missing from the header.
    """
    text = path.read_text(encoding="utf-8-sig")
    lines = [line for line in text.splitlines() if line.strip() and not line.startswith("#")]
    reader = csv.reader(lines)
    header = [normalise_header(name) for name in next(reader, [])]
    missing = [column for column in REQUIRED_COLUMNS if column not in header]
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")
    return [_to_record(header, values) for values in reader]


def normalise_header(name: str) -> str:
    """Turn a raw header such as `` Order ID `` into ``order_id``."""
    return "_".join(name.lower().split())


def _to_record(header: list[str], values: list[str]) -> dict[str, str]:
    cells = dict(zip(header, values))
    return {column: cells.get(column, "").strip() for column in REQUIRED_COLUMNS}


def clean_row(raw: Mapping[str, str]) -> OrderRow | None:
    """Normalise one raw record, or return None if it must be dropped.

    Args:
        raw: A record as produced by ``load_records``.

    Returns:
        The cleaned row, or None when the order id, amount or date is missing or invalid.
    """
    order_id = raw["order_id"].upper()
    amount = parse_amount(raw["amount"])
    order_date = parse_date(raw["order_date"])
    if not order_id or amount is None or order_date is None:
        return None
    return OrderRow(
        order_id=order_id,
        customer_email=clean_email(raw["customer_email"]),
        amount=amount,
        currency=clean_currency(raw["currency"], raw["amount"]),
        order_date=order_date,
        status=clean_status(raw["status"]),
        updated_at=parse_updated_at(raw["updated_at"]),
    )


def clean_email(raw: str) -> str:
    """Lowercase an email, or return an empty string if it lacks one ``@`` with text on both sides."""
    email = raw.strip().lower()
    local, separator, domain = email.partition("@")
    if not separator or not local or not domain or "@" in domain:
        return ""
    return email


def parse_amount(raw: str) -> Decimal | None:
    """Parse a money amount with symbols, separators and accounting negatives.

    Args:
        raw: The amount as exported, e.g. ``$1,234.50`` or ``(12.50)``.

    Returns:
        The amount rounded half away from zero to two decimals, or None if unparseable.
    """
    text = re.sub(r"[$€£\s]", "", raw)
    if text.startswith("(") and text.endswith(")"):
        is_negative, number = True, text[1:-1]
    elif text.startswith("-"):
        is_negative, number = True, text[1:]
    else:
        is_negative, number = False, text
    plain = _normalise_number(number)
    if plain is None:
        return None
    try:
        magnitude = Decimal(plain).quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None
    return -magnitude if is_negative and magnitude else magnitude


def _normalise_number(text: str) -> str | None:
    """Turn a number with separators into a plain ``123.45`` string, or None if invalid."""
    decimal = _decimal_separator(text)
    thousands = {".": ",", ",": ".", None: ","}[decimal]
    cleaned = text.replace(thousands, "")
    if decimal is not None:
        cleaned = cleaned.replace(decimal, ".")
    return cleaned if _PLAIN_NUMBER.fullmatch(cleaned) else None


def _decimal_separator(text: str) -> str | None:
    """Pick the decimal separator: the last of ``.``/``,`` when both appear, else per the spec."""
    last_dot, last_comma = text.rfind("."), text.rfind(",")
    if last_dot >= 0 and last_comma >= 0:
        return "." if last_dot > last_comma else ","
    if last_comma >= 0:
        return "," if re.fullmatch(r"[0-9]{2}", text[last_comma + 1 :]) else None
    return "." if last_dot >= 0 else None


def clean_currency(raw_currency: str, raw_amount: str) -> str:
    """Return the ISO code for the currency field, falling back to a symbol in the amount.

    Args:
        raw_currency: The currency column, possibly empty or a symbol.
        raw_amount: The raw amount, used when the currency column is empty.

    Returns:
        A currency code, defaulting to ``USD`` when neither field gives one.
    """
    code = raw_currency.strip().upper()
    if not code:
        code = next((CURRENCY_SYMBOLS[char] for char in raw_amount if char in CURRENCY_SYMBOLS), "USD")
    return CURRENCY_SYMBOLS.get(code, code)


def parse_date(raw: str) -> date | None:
    """Parse one of the accepted order date formats.

    Args:
        raw: The date as exported.

    Returns:
        The date, or None if the format is not accepted or the date does not exist.
    """
    text = " ".join(raw.lower().split())
    parts = _date_parts(text)
    if parts is None:
        return None
    try:
        return date(*parts)
    except ValueError:
        return None


def _date_parts(text: str) -> tuple[int, int, int] | None:
    """Return (year, month, day) for a lowercased, whitespace-normalised date, or None."""
    if match := _ISO_DATE.fullmatch(text):
        return int(match[1]), int(match[3]), int(match[4])
    if match := _DAY_FIRST_DOTTED.fullmatch(text):
        return int(match[3]), int(match[2]), int(match[1])
    if match := _MONTH_FIRST_SLASHED.fullmatch(text):
        return int(match[3]), int(match[1]), int(match[2])
    if match := _MONTH_NAME_FIRST.fullmatch(text):
        return _named_month_parts(match[3], match[1], match[2])
    if match := _DAY_FIRST_MONTH_NAME.fullmatch(text):
        return _named_month_parts(match[3], match[2], match[1])
    return None


def _named_month_parts(year: str, month_name: str, day: str) -> tuple[int, int, int] | None:
    month = MONTHS.get(month_name)
    if month is None:
        return None
    return int(year), month, int(day)


def clean_status(raw: str) -> str:
    """Normalise an order status to one of the allowed values, or ``unknown``."""
    status = raw.strip().lower()
    if status == "canceled":
        status = "cancelled"
    return status if status in ALLOWED_STATUSES else "unknown"


def parse_updated_at(raw: str) -> datetime:
    """Parse ``updated_at`` for de-duplication, treating empty or invalid values as oldest.

    Args:
        raw: A timestamp such as ``2026-03-04T10:00:00Z`` or ``2026-03-04 10:00:00``.

    Returns:
        A naive datetime, or ``datetime.min`` when the value is empty or invalid.
    """
    text = raw.strip().rstrip("Z").replace("T", " ")
    try:
        return datetime.strptime(text, _UPDATED_AT_FORMAT)
    except ValueError:
        return datetime.min


def keep_latest_per_order(rows: Iterable[OrderRow]) -> list[OrderRow]:
    """Keep one row per order id: the latest ``updated_at``, the later row on ties."""
    latest: dict[str, OrderRow] = {}
    for row in rows:
        current = latest.get(row.order_id)
        if current is None or row.updated_at >= current.updated_at:
            latest[row.order_id] = row
    return list(latest.values())


def write_rows(path: Path, rows: Iterable[OrderRow]) -> None:
    """Write cleaned rows, sorted by order date then order id, as CSV.

    Args:
        path: Destination file; overwritten if it exists.
        rows: The rows to write.
    """
    ordered = sorted(rows, key=lambda row: (row.order_date, row.order_id))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(OUTPUT_COLUMNS)
        for row in ordered:
            writer.writerow(
                [
                    row.order_id,
                    row.customer_email,
                    f"{row.amount:.2f}",
                    row.currency,
                    row.order_date.isoformat(),
                    row.status,
                ]
            )


def main() -> None:
    """Run the cleaner from the command line."""
    if len(sys.argv) != 3:
        sys.exit("usage: python3 clean.py INPUT.csv OUTPUT.csv")
    try:
        records = load_records(Path(sys.argv[1]))
    except ValueError as exc:
        sys.exit(f"error: {exc}")
    rows = [row for record in records if (row := clean_row(record)) is not None]
    write_rows(Path(sys.argv[2]), keep_latest_per_order(rows))


if __name__ == "__main__":
    main()
