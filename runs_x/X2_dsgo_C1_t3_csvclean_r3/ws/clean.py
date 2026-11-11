#!/usr/bin/env python3
"""Clean a messy order export CSV.

Usage: python3 clean.py INPUT.csv OUTPUT.csv
"""

import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

CURRENCY_SYMBOLS = {"$": "USD", "\u20ac": "EUR", "\u00a3": "GBP"}

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
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

# A plain number: digits with optional separators between digit groups.
NUMERIC_RE = re.compile(r"[0-9]+(?:[.,][0-9]+)*")

UPDATED_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})Z?")


def normalise_header(name):
    return name.strip().lower().replace(" ", "_")


def make_date(year, month, day):
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_amount(raw):
    """Return (formatted_amount, currency_symbol) or (None, None)."""
    text = raw.strip()
    if not text:
        return None, None

    symbol = None
    for char in text:
        if char in CURRENCY_SYMBOLS:
            symbol = char
            break

    number = "".join(
        char for char in text if char not in CURRENCY_SYMBOLS and not char.isspace()
    )
    if not number:
        return None, None

    negative = False
    if number.startswith("(") and number.endswith(")"):
        negative = True
        number = number[1:-1]
    if "(" in number or ")" in number:
        return None, None

    if not NUMERIC_RE.fullmatch(number):
        return None, None

    has_dot = "." in number
    has_comma = "," in number

    if has_dot and has_comma:
        decimal_sep = "." if number.rfind(".") > number.rfind(",") else ","
    elif has_comma:
        digits_after_last_comma = len(number) - number.rfind(",") - 1
        decimal_sep = "," if digits_after_last_comma == 2 else None
    elif has_dot:
        decimal_sep = "."
    else:
        decimal_sep = None

    if decimal_sep is None:
        normalised = number.replace(".", "").replace(",", "")
    else:
        index = number.rfind(decimal_sep)
        integer_part = number[:index]
        fraction_part = number[index + 1:]
        integer_part = integer_part.replace(".", "").replace(",", "")
        normalised = integer_part + "." + fraction_part

    try:
        with localcontext() as context:
            context.prec = max(28, len(normalised) + 5)
            value = Decimal(normalised)
            if negative:
                value = -value
            rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None, None

    if rounded == 0:
        rounded = abs(rounded)
    return format(rounded, "f"), symbol


def parse_order_date(raw):
    """Return a datetime.date or None."""
    text = raw.strip()
    if not text:
        return None

    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return make_date(year, month, day)

    match = re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})", text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return make_date(year, month, day)

    match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if match:
        day, month, year = (int(part) for part in match.groups())
        return make_date(year, month, day)

    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if match:
        month, day, year = (int(part) for part in match.groups())
        return make_date(year, month, day)

    match = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2})\s*,\s*(\d{4})", text)
    if match:
        month_name, day, year = match.groups()
        month = MONTH_NAMES.get(month_name.lower())
        if month is None:
            return None
        return make_date(int(year), month, int(day))

    match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text)
    if match:
        day, month_name, year = match.groups()
        month = MONTH_NAMES.get(month_name.lower())
        if month is None:
            return None
        return make_date(int(year), month, int(day))

    return None


def parse_updated_at(raw):
    """Return a comparable datetime; empty or invalid means oldest possible."""
    text = raw.strip()
    if not text:
        return datetime.min

    match = UPDATED_RE.fullmatch(text)
    if not match:
        return datetime.min

    year, month, day, hour, minute, second = (int(part) for part in match.groups())
    try:
        return datetime(year, month, day, hour, minute, second)
    except ValueError:
        return datetime.min


def clean_rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        raw_text = handle.read()

    lines = [
        line
        for line in raw_text.splitlines()
        if line.strip() != "" and not line.startswith("#")
    ]

    reader = csv.reader(lines)
    rows = list(reader)
    if not rows:
        return []

    header_map = {}
    for index, name in enumerate(rows[0]):
        key = normalise_header(name)
        if key not in header_map:
            header_map[key] = index

    def get(row, column):
        index = header_map.get(column)
        if index is None or index >= len(row):
            return ""
        return row[index].strip()

    cleaned = {}
    for position, row in enumerate(rows[1:]):
        order_id = get(row, "order_id").upper()
        if not order_id:
            continue

        amount, symbol = parse_amount(get(row, "amount"))
        if amount is None:
            continue

        order_date = parse_order_date(get(row, "order_date"))
        if order_date is None:
            continue

        email = get(row, "customer_email").lower()
        if email.count("@") != 1:
            email = ""
        else:
            local, _, domain = email.partition("@")
            if not local or not domain:
                email = ""

        currency = get(row, "currency").upper()
        currency = CURRENCY_SYMBOLS.get(currency, currency)
        if not currency:
            currency = CURRENCY_SYMBOLS.get(symbol, "USD")

        status = get(row, "status").lower()
        if status == "canceled":
            status = "cancelled"
        if status not in ALLOWED_STATUSES:
            status = "unknown"

        updated_at = parse_updated_at(get(row, "updated_at"))

        record = {
            "order_id": order_id,
            "customer_email": email,
            "amount": amount,
            "currency": currency,
            "order_date": order_date.isoformat(),
            "status": status,
            "_updated_at": updated_at,
            "_position": position,
        }

        previous = cleaned.get(order_id)
        if previous is None or (updated_at, position) >= (
            previous["_updated_at"],
            previous["_position"],
        ):
            cleaned[order_id] = record

    return list(cleaned.values())


def write_output(path, records):
    records.sort(key=lambda record: (record["order_date"], record["order_id"]))
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(
            [
                "order_id",
                "customer_email",
                "amount",
                "currency",
                "order_date",
                "status",
            ]
        )
        for record in records:
            writer.writerow(
                [
                    record["order_id"],
                    record["customer_email"],
                    record["amount"],
                    record["currency"],
                    record["order_date"],
                    record["status"],
                ]
            )


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("Usage: python3 clean.py INPUT.csv OUTPUT.csv\n")
        return 2
    records = clean_rows(argv[1])
    write_output(argv[2], records)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
