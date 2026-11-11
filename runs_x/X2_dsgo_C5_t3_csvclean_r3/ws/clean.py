#!/usr/bin/env python3
"""Clean a shop order export CSV.

Usage:
    python3 clean.py INPUT.csv OUTPUT.csv
"""

import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


SYMBOLS = "$€£"
SYMBOL_TO_CURRENCY = {"$": "USD", "€": "EUR", "£": "GBP"}
REQUIRED_COLUMNS = (
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
ALLOWED_STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}

MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


def normalise_header(name):
    return name.strip().lower().replace(" ", "_")


def clean_email(value):
    email = value.strip().lower()
    if email.count("@") != 1:
        return ""
    local, domain = email.split("@")
    if not local or not domain:
        return ""
    return email


def parse_amount(value):
    """Return (formatted amount or None, currency symbol or None)."""
    text = value.strip()
    if not text:
        return None, None

    symbol = next((ch for ch in text if ch in SYMBOLS), None)

    # Remove currency symbols and all whitespace.
    work = "".join(ch for ch in text if ch not in SYMBOLS and not ch.isspace())

    negative = False
    if work.startswith("(") and work.endswith(")"):
        negative = True
        work = work[1:-1]

    if work.startswith("-"):
        negative = True
        work = work[1:]
    elif work.startswith("+"):
        work = work[1:]

    if not work or not re.fullmatch(r"[0-9.,]+", work):
        return None, symbol

    has_dot = "." in work
    has_comma = "," in work

    if has_dot and has_comma:
        if work.rfind(".") > work.rfind(","):
            # Dot is the decimal separator, comma is thousands.
            work = work.replace(",", "")
            if work.count(".") != 1:
                return None, symbol
        else:
            # Comma is the decimal separator, dot is thousands.
            work = work.replace(".", "")
            last = work.rfind(",")
            prefix = work[:last].replace(",", "")
            tail = work[last + 1:]
            if not prefix:
                prefix = "0"
            if not prefix.isdigit() or not tail.isdigit():
                return None, symbol
            work = prefix + "." + tail
    elif has_comma:
        last = work.rfind(",")
        tail = work[last + 1:]
        if len(tail) == 2 and tail.isdigit():
            # Comma is the decimal separator.
            prefix = work[:last].replace(",", "")
            if not prefix:
                prefix = "0"
            if not prefix.isdigit():
                return None, symbol
            work = prefix + "." + tail
        else:
            # Comma is a thousands separator.
            work = work.replace(",", "")
    elif has_dot:
        if work.count(".") != 1:
            return None, symbol

    if not re.fullmatch(r"\d*\.?\d*", work) or not any(ch.isdigit() for ch in work):
        return None, symbol

    try:
        amount = Decimal(work)
        if negative:
            amount = -amount
        amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if amount == 0:
            amount = abs(amount)
    except (InvalidOperation, ValueError):
        return None, symbol

    return format(amount, ".2f"), symbol


def parse_date(value):
    """Return YYYY-MM-DD, or None when the date is missing/invalid."""
    text = value.strip()
    if not text:
        return None

    year = month = day = None

    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m:
        year, month, day = (int(part) for part in m.groups())
    if year is None:
        m = re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})", text)
        if m:
            year, month, day = (int(part) for part in m.groups())
    if year is None:
        m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
        if m:
            day, month, year = (int(part) for part in m.groups())
    if year is None:
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
        if m:
            month, day, year = (int(part) for part in m.groups())
    if year is None:
        # "Mar 4, 2026" / "March 4, 2026" (comma required)
        m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", text)
        if m:
            month_name, day_text, year_text = m.groups()
            month = MONTHS.get(month_name.lower())
            day = int(day_text)
            year = int(year_text)
            if month is None:
                return None
    if year is None:
        # "4 Mar 2026" / "4 March 2026"
        m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+),?\s+(\d{4})", text)
        if m:
            day_text, month_name, year_text = m.groups()
            month = MONTHS.get(month_name.lower())
            day = int(day_text)
            year = int(year_text)
            if month is None:
                return None

    if year is None:
        return None

    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def parse_updated_at(value):
    """Return a datetime, or None when empty/unparseable."""
    text = value.strip()
    if not text:
        return None
    m = re.fullmatch(
        r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})Z?", text
    )
    if not m:
        return None
    try:
        return datetime(*(int(part) for part in m.groups()))
    except ValueError:
        return None


def cell(row, indexes, name):
    position = indexes.get(name)
    if position is None or position >= len(row):
        return ""
    return row[position]


def clean_rows(indexes, rows):
    best = {}

    for line_number, row in enumerate(rows, start=1):
        order_id = cell(row, indexes, "order_id").strip().upper()
        if not order_id:
            continue

        amount_text, symbol = parse_amount(cell(row, indexes, "amount"))
        if amount_text is None:
            continue

        order_date = parse_date(cell(row, indexes, "order_date"))
        if order_date is None:
            continue

        email = clean_email(cell(row, indexes, "customer_email"))

        currency_raw = cell(row, indexes, "currency").strip()
        if currency_raw:
            currency = SYMBOL_TO_CURRENCY.get(currency_raw, currency_raw.upper())
        else:
            currency = SYMBOL_TO_CURRENCY.get(symbol, "USD")

        status = cell(row, indexes, "status").strip().lower()
        if status == "canceled":
            status = "cancelled"
        if status not in ALLOWED_STATUSES:
            status = "unknown"

        updated_at = parse_updated_at(cell(row, indexes, "updated_at"))
        sort_key = (updated_at or datetime.min, line_number)

        record = {
            "order_id": order_id,
            "customer_email": email,
            "amount": amount_text,
            "currency": currency,
            "order_date": order_date,
            "status": status,
        }

        previous = best.get(order_id)
        if previous is None or sort_key > previous[0]:
            best[order_id] = (sort_key, record)

    return [entry[1] for entry in best.values()]


def read_input(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        text = handle.read()

    lines = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if line[0] == "#":
            continue
        lines.append(line)

    reader = csv.reader(lines)
    try:
        header = next(reader)
    except StopIteration:
        return [], []

    indexes = {}
    for position, name in enumerate(header):
        key = normalise_header(name)
        if key in REQUIRED_COLUMNS and key not in indexes:
            indexes[key] = position

    return indexes, list(reader)


def write_output(path, records):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(OUTPUT_COLUMNS)
        for record in records:
            writer.writerow([record[column] for column in OUTPUT_COLUMNS])


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("Usage: python3 clean.py INPUT.csv OUTPUT.csv\n")
        return 2

    indexes, rows = read_input(argv[1])
    records = clean_rows(indexes, rows)
    records.sort(key=lambda record: (record["order_date"], record["order_id"]))
    write_output(argv[2], records)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
