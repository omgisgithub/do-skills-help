#!/usr/bin/env python3
"""Clean a messy order export CSV.

Usage:
    python3 clean.py INPUT.csv OUTPUT.csv

The cleaner is intentionally data-driven: it discovers columns by their
normalised header names instead of relying on a fixed column order.
"""

from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from pathlib import Path
from typing import Optional, Sequence

OUTPUT_COLUMNS = [
    "order_id",
    "customer_email",
    "amount",
    "currency",
    "order_date",
    "status",
]
INPUT_COLUMNS = OUTPUT_COLUMNS + ["updated_at"]

CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
ALLOWED_STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}

MONTH_NAMES = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

YEAR_FIRST_DATE = re.compile(r"^(\d{4})([-/])(\d{1,2})\2(\d{1,2})$")
DOTTED_DATE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")
SLASHED_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
MONTH_FIRST_DATE = re.compile(r"^([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})$")
DAY_FIRST_DATE = re.compile(r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$")
UPDATED_AT = re.compile(r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})Z?$")


@dataclass(frozen=True)
class Order:
    """A cleaned order row that survived validation."""

    order_id: str
    customer_email: str
    amount: Decimal
    currency: str
    order_date: date
    status: str
    updated_at: Optional[datetime]
    position: int

    @property
    def updated_key(self) -> datetime:
        """Return the de-duplication timestamp, with empty treated as oldest."""
        return self.updated_at if self.updated_at is not None else datetime.min


def normalize_header(name: str) -> str:
    """Turn a raw header cell into its canonical column name."""
    return re.sub(r"\s+", "_", name.strip().lower())


def normalize_order_id(raw: str) -> str:
    """Normalise an order identifier."""
    return raw.strip().upper()


def normalize_email(raw: str) -> str:
    """Normalise an email address, returning empty for malformed values."""
    email = raw.strip().lower()
    parts = email.split("@")
    if len(parts) == 2 and parts[0] and parts[1]:
        return email
    return ""


def first_currency_symbol(raw: str) -> Optional[str]:
    """Return the first currency symbol found in a raw amount, if any."""
    for character in raw:
        if character in CURRENCY_SYMBOLS:
            return character
    return None


def parse_amount(raw: str) -> Optional[Decimal]:
    """Parse a messy amount into a value rounded to two decimal places.

    Args:
        raw: The amount cell as it appeared in the input.

    Returns:
        The parsed amount, or ``None`` when the value is empty or unparseable.
    """
    text = raw.strip()
    if not text:
        return None

    for symbol in CURRENCY_SYMBOLS:
        text = text.replace(symbol, "")
    text = re.sub(r"\s+", "", text)
    if not text:
        return None

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    if text.startswith("-"):
        negative = True
        text = text[1:]
    elif text.startswith("+"):
        text = text[1:]

    if not text or any(character not in "0123456789.," for character in text):
        return None

    has_dot = "." in text
    has_comma = "," in text

    if has_dot and has_comma:
        if text.rfind(".") > text.rfind(","):
            decimal_separator = "."
            thousands_separator = ","
        else:
            decimal_separator = ","
            thousands_separator = "."
        text = text.replace(thousands_separator, "")
    elif has_comma:
        last_comma = text.rfind(",")
        tail = text[last_comma + 1 :]
        if len(tail) == 2 and tail.isdigit():
            text = text[:last_comma].replace(",", "") + "." + tail
            decimal_separator = None
        else:
            text = text.replace(",", "")
            decimal_separator = None
    elif has_dot:
        decimal_separator = "."
    else:
        decimal_separator = None

    if decimal_separator == ".":
        if text.count(".") > 1:
            return None
    elif decimal_separator == ",":
        if text.count(",") > 1:
            return None
        text = text.replace(",", ".")

    if text.endswith("."):
        text = text[:-1]
    if not re.fullmatch(r"\d+(?:\.\d*)?|\.\d+", text):
        return None

    try:
        with localcontext() as context:
            context.prec = 50
            value = Decimal(text)
            if negative:
                value = -value
            value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None

    # Avoid rendering "-0.00" for negative zero.
    if value == 0:
        value = abs(value)
    return value


def normalize_currency(raw_currency: str, raw_amount: str) -> str:
    """Resolve a currency code from the currency cell or amount symbol."""
    currency = raw_currency.strip().upper()
    if not currency:
        symbol = first_currency_symbol(raw_amount)
        if symbol is not None:
            return CURRENCY_SYMBOLS[symbol]
        return "USD"
    if currency in CURRENCY_SYMBOLS:
        return CURRENCY_SYMBOLS[currency]
    return currency


def _safe_date(year: int, month: int, day: int) -> Optional[date]:
    """Build a date, returning ``None`` when the components are invalid."""
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_order_date(raw: str) -> Optional[date]:
    """Parse one of the accepted order-date formats."""
    text = raw.strip()
    if not text:
        return None

    match = YEAR_FIRST_DATE.match(text)
    if match:
        return _safe_date(int(match.group(1)), int(match.group(3)), int(match.group(4)))

    match = DOTTED_DATE.match(text)
    if match:
        return _safe_date(int(match.group(3)), int(match.group(2)), int(match.group(1)))

    match = SLASHED_DATE.match(text)
    if match:
        return _safe_date(int(match.group(3)), int(match.group(1)), int(match.group(2)))

    match = MONTH_FIRST_DATE.match(text)
    if match:
        month = MONTH_NAMES.get(match.group(1).lower())
        if month is None:
            return None
        return _safe_date(int(match.group(3)), month, int(match.group(2)))

    match = DAY_FIRST_DATE.match(text)
    if match:
        month = MONTH_NAMES.get(match.group(2).lower())
        if month is None:
            return None
        return _safe_date(int(match.group(3)), month, int(match.group(1)))

    return None


def normalize_status(raw: str) -> str:
    """Normalise a status, mapping unknown values to ``unknown``."""
    status = raw.strip().lower()
    if status == "canceled":
        status = "cancelled"
    if status in ALLOWED_STATUSES:
        return status
    return "unknown"


def parse_updated_at(raw: str) -> Optional[datetime]:
    """Parse an ``updated_at`` timestamp, or return ``None`` if unusable."""
    text = raw.strip()
    if not text:
        return None
    match = UPDATED_AT.match(text)
    if not match:
        return None
    try:
        return datetime(*(int(part) for part in match.groups()))
    except ValueError:
        return None


def build_order(
    row: Sequence[str], columns: dict[str, Optional[int]], position: int
) -> Optional[Order]:
    """Convert a raw CSV row into an :class:`Order`, or drop it."""

    def cell(name: str) -> str:
        index = columns.get(name)
        if index is None or index >= len(row):
            return ""
        return row[index].strip()

    order_id = normalize_order_id(cell("order_id"))
    if not order_id:
        return None

    raw_amount = cell("amount")
    amount = parse_amount(raw_amount)
    if amount is None:
        return None

    order_date = parse_order_date(cell("order_date"))
    if order_date is None:
        return None

    return Order(
        order_id=order_id,
        customer_email=normalize_email(cell("customer_email")),
        amount=amount,
        currency=normalize_currency(cell("currency"), raw_amount),
        order_date=order_date,
        status=normalize_status(cell("status")),
        updated_at=parse_updated_at(cell("updated_at")),
        position=position,
    )


def map_columns(header: Sequence[str]) -> dict[str, Optional[int]]:
    """Map canonical column names to their indices in the header."""
    normalized = [normalize_header(name) for name in header]
    columns: dict[str, Optional[int]] = {}
    for name in INPUT_COLUMNS:
        try:
            columns[name] = normalized.index(name)
        except ValueError:
            columns[name] = None
    return columns


def read_csv(path: Path) -> list[list[str]]:
    """Read the input CSV, skipping blank and comment lines."""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        physical_lines = handle.readlines()

    kept_lines = []
    for line in physical_lines:
        content = line.rstrip("\r\n")
        if not content.strip():
            continue
        if content.startswith("#"):
            continue
        kept_lines.append(line)

    return list(csv.reader(kept_lines))


def deduplicate(orders: Sequence[Order]) -> list[Order]:
    """Keep the latest update for each order id, with later rows winning ties."""
    latest: dict[str, Order] = {}
    for order in orders:
        current = latest.get(order.order_id)
        if current is None or (order.updated_key, order.position) >= (
            current.updated_key,
            current.position,
        ):
            latest[order.order_id] = order
    return sorted(latest.values(), key=lambda order: (order.order_date, order.order_id))


def write_csv(path: Path, orders: Sequence[Order]) -> None:
    """Write the cleaned orders in the required output format."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(OUTPUT_COLUMNS)
        for order in orders:
            writer.writerow(
                [
                    order.order_id,
                    order.customer_email,
                    format(order.amount, "f"),
                    order.currency,
                    order.order_date.isoformat(),
                    order.status,
                ]
            )


def clean_file(input_path: Path, output_path: Path) -> None:
    """Clean ``input_path`` and write the result to ``output_path``."""
    rows = read_csv(input_path)
    if not rows:
        write_csv(output_path, [])
        return

    columns = map_columns(rows[0])
    orders = []
    for position, row in enumerate(rows[1:]):
        order = build_order(row, columns, position)
        if order is not None:
            orders.append(order)

    write_csv(output_path, deduplicate(orders))


def main(argv: Sequence[str]) -> int:
    """Run the command-line interface."""
    if len(argv) != 3:
        print("usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2

    try:
        clean_file(Path(argv[1]), Path(argv[2]))
    except OSError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
