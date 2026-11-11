#!/usr/bin/env python3
"""Clean a shop order export.

Usage:
    python3 clean.py INPUT.csv OUTPUT.csv

Reads a messy order export, normalises its fields, de-duplicates rows by
order id and writes a clean CSV.  Standard library only; works on Python 3.9.
"""

from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable, Optional

FIELDS = (
    "order_id",
    "customer_email",
    "amount",
    "currency",
    "order_date",
    "status",
    "updated_at",
)

OUTPUT_HEADER = [
    "order_id",
    "customer_email",
    "amount",
    "currency",
    "order_date",
    "status",
]

SYMBOL_CURRENCIES = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
}

ALLOWED_STATUSES = {
    "pending",
    "paid",
    "shipped",
    "cancelled",
    "refunded",
}

MONTHS = {
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

DATE_YEAR_FIRST = re.compile(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$")
DATE_DAY_FIRST_DOT = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")
DATE_MONTH_FIRST_SLASH = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
DATE_MONTH_NAME_FIRST = re.compile(r"^([A-Za-z]+)\.?\s+(\d{1,2})\s*,?\s*(\d{4})$")
DATE_MONTH_NAME_LAST = re.compile(r"^(\d{1,2})\s+([A-Za-z]+)\.?\s*,?\s*(\d{4})$")

UPDATED_AT = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})Z?$"
)


@dataclass
class CleanRow:
    """A fully normalised row that will appear in the output."""

    order_id: str
    customer_email: str
    amount: Decimal
    currency: str
    order_date: str
    status: str
    updated_key: tuple
    line_number: int


def normalise_header(name: str) -> str:
    """Normalise a header cell so it can be matched to a known field."""
    return "_".join(name.strip().lower().split())


def normalise_order_id(raw: str) -> str:
    """Trim and uppercase an order id."""
    return raw.strip().upper()


def normalise_email(raw: str) -> str:
    """Trim and lowercase an email, blanking out clearly invalid values."""
    email = raw.strip().lower()
    parts = email.split("@")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return ""
    return email


def parse_amount(raw: str) -> Optional[Decimal]:
    """Parse a messy amount into a Decimal rounded to two places.

    Returns ``None`` when the value is empty or cannot be parsed.
    """
    text = raw.strip()
    if not text:
        return None

    cleaned = text
    for symbol in SYMBOL_CURRENCIES:
        cleaned = cleaned.replace(symbol, "")
    cleaned = "".join(cleaned.split())
    if not cleaned:
        return None

    negative = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        negative = True
        cleaned = cleaned[1:-1]
    if cleaned.startswith("-"):
        negative = True
        cleaned = cleaned[1:]
    elif cleaned.startswith("+"):
        cleaned = cleaned[1:]
    if not cleaned:
        return None
    if any(char not in "0123456789.," for char in cleaned):
        return None

    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            head, _, tail = cleaned.rpartition(",")
            cleaned = head.replace(".", "").replace(",", "") + "." + tail
        else:
            head, _, tail = cleaned.rpartition(".")
            cleaned = head.replace(".", "").replace(",", "") + "." + tail
    elif "," in cleaned:
        last_comma = cleaned.rfind(",")
        if len(cleaned) - last_comma - 1 == 2:
            cleaned = cleaned[:last_comma].replace(",", "") + "." + cleaned[last_comma + 1:]
        else:
            cleaned = cleaned.replace(",", "")

    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    if not value.is_finite():
        return None
    if negative:
        value = -value
    try:
        rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None
    if rounded == 0:
        rounded = Decimal("0.00")
    return rounded


def currency_from_amount(raw: str) -> Optional[str]:
    """Return the first currency symbol found in an amount, if any."""
    for char in raw:
        if char in SYMBOL_CURRENCIES:
            return SYMBOL_CURRENCIES[char]
    return None


def normalise_currency(raw: str, raw_amount: str) -> str:
    """Normalise a currency field, falling back to the amount's symbol."""
    currency = raw.strip().upper()
    if not currency:
        from_amount = currency_from_amount(raw_amount)
        return from_amount if from_amount is not None else "USD"
    if currency in SYMBOL_CURRENCIES:
        return SYMBOL_CURRENCIES[currency]
    return currency


def build_date(year: int, month: int, day: int) -> Optional[str]:
    """Return an ISO date string, or ``None`` when the date is invalid."""
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def parse_order_date(raw: str) -> Optional[str]:
    """Parse a supported date format and return ``YYYY-MM-DD``."""
    text = raw.strip()
    if not text:
        return None

    match = DATE_YEAR_FIRST.match(text)
    if match:
        return build_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))

    match = DATE_DAY_FIRST_DOT.match(text)
    if match:
        return build_date(int(match.group(3)), int(match.group(2)), int(match.group(1)))

    match = DATE_MONTH_FIRST_SLASH.match(text)
    if match:
        return build_date(int(match.group(3)), int(match.group(1)), int(match.group(2)))

    match = DATE_MONTH_NAME_FIRST.match(text)
    if match:
        month = MONTHS.get(match.group(1).lower())
        if month is None:
            return None
        return build_date(int(match.group(3)), month, int(match.group(2)))

    match = DATE_MONTH_NAME_LAST.match(text)
    if match:
        month = MONTHS.get(match.group(2).lower())
        if month is None:
            return None
        return build_date(int(match.group(3)), month, int(match.group(1)))

    return None


def normalise_status(raw: str) -> str:
    """Normalise a status, mapping anything unrecognised to ``unknown``."""
    status = raw.strip().lower()
    if status == "canceled":
        status = "cancelled"
    if status in ALLOWED_STATUSES:
        return status
    return "unknown"


def parse_updated_at(raw: str) -> tuple:
    """Return a sortable key for ``updated_at``; empty values sort oldest."""
    text = raw.strip()
    if not text:
        return (0, 0, 0, 0, 0, 0)
    match = UPDATED_AT.match(text)
    if not match:
        return (0, 0, 0, 0, 0, 0)
    year, month, day, hour, minute, second = (int(part) for part in match.groups())
    try:
        date(year, month, day)
    except ValueError:
        return (0, 0, 0, 0, 0, 0)
    if hour > 23 or minute > 59 or second > 59:
        return (0, 0, 0, 0, 0, 0)
    return (year, month, day, hour, minute, second)


def read_data_rows(path: str) -> Iterable[list]:
    """Yield CSV rows from *path*, skipping blank and comment lines."""
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        lines = [
            line
            for line in handle.read().splitlines()
            if line.strip() and not line.startswith("#")
        ]
    return csv.reader(lines)


def cell(row: list, index: Optional[int], default: str = "") -> str:
    """Return a cell value safely, using *default* for missing columns."""
    if index is None or index >= len(row):
        return default
    return row[index]


def clean_rows(rows: Iterable[list]) -> list:
    """Normalise all data rows and de-duplicate them by order id."""
    header: Optional[list] = None
    column_index: dict = {}
    cleaned: list = []

    for line_number, row in enumerate(rows, start=1):
        if header is None:
            header = row
            for position, name in enumerate(header):
                field = normalise_header(name)
                if field in FIELDS and field not in column_index:
                    column_index[field] = position
            continue

        if not row:
            continue

        order_id = normalise_order_id(cell(row, column_index.get("order_id")))
        if not order_id:
            continue

        raw_amount = cell(row, column_index.get("amount"))
        amount = parse_amount(raw_amount)
        if amount is None:
            continue

        order_date = parse_order_date(cell(row, column_index.get("order_date")))
        if order_date is None:
            continue

        cleaned.append(
            CleanRow(
                order_id=order_id,
                customer_email=normalise_email(
                    cell(row, column_index.get("customer_email"))
                ),
                amount=amount,
                currency=normalise_currency(
                    cell(row, column_index.get("currency")), raw_amount
                ),
                order_date=order_date,
                status=normalise_status(cell(row, column_index.get("status"))),
                updated_key=parse_updated_at(
                    cell(row, column_index.get("updated_at"))
                ),
                line_number=line_number,
            )
        )

    best: dict = {}
    for row in cleaned:
        key = (row.updated_key, row.line_number)
        current = best.get(row.order_id)
        if current is None or key > (current.updated_key, current.line_number):
            best[row.order_id] = row

    return list(best.values())


def write_output(path: str, rows: list) -> None:
    """Write cleaned rows sorted by order date and order id."""
    ordered = sorted(rows, key=lambda row: (row.order_date, row.order_id))
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(OUTPUT_HEADER)
        for row in ordered:
            writer.writerow(
                [
                    row.order_id,
                    row.customer_email,
                    format(row.amount, ".2f"),
                    row.currency,
                    row.order_date,
                    row.status,
                ]
            )


def main(argv: list) -> int:
    """Run the cleaner using command-line arguments."""
    if len(argv) != 3:
        print("usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2

    input_path, output_path = argv[1], argv[2]
    rows = clean_rows(read_data_rows(input_path))
    write_output(output_path, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
