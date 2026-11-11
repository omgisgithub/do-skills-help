#!/usr/bin/env python3
"""Clean a shop order export CSV.

Usage: python3 clean.py INPUT.csv OUTPUT.csv
"""

import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext


SYMBOL_CURRENCIES = {"$": "USD", "\u20ac": "EUR", "\u00a3": "GBP"}
ALLOWED_STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

FIELDS = [
    "order_id",
    "customer_email",
    "amount",
    "currency",
    "order_date",
    "status",
    "updated_at",
]
OUTPUT_FIELDS = [
    "order_id",
    "customer_email",
    "amount",
    "currency",
    "order_date",
    "status",
]


def normalise_header(name):
    return re.sub(r"\s+", "_", name.strip().lower())


def read_rows(path):
    """Yield CSV rows, skipping blank lines and comment lines."""
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        def useful_lines():
            for line in handle:
                if not line.strip():
                    continue
                if line[0] == "#":
                    continue
                yield line

        reader = csv.reader(useful_lines())
        for row in reader:
            if not row:
                continue
            yield row


def parse_email(raw):
    value = raw.strip().lower()
    if value.count("@") != 1:
        return ""
    local, domain = value.split("@")
    if not local or not domain:
        return ""
    return value


def parse_amount(raw):
    """Return a Decimal (rounded to cents) or None if unparseable."""
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None

    # Remove currency symbols (they may appear anywhere) and whitespace.
    for symbol in SYMBOL_CURRENCIES:
        text = text.replace(symbol, "")
    text = re.sub(r"\s+", "", text)
    if not text:
        return None

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    elif text.startswith("-"):
        negative = True
        text = text[1:]
    elif text.startswith("+"):
        text = text[1:]

    if not text or any(ch not in "0123456789.," for ch in text):
        return None

    has_dot = "." in text
    has_comma = "," in text

    if has_dot and has_comma:
        decimal = "." if text.rfind(".") > text.rfind(",") else ","
    elif has_comma:
        last = text.rfind(",")
        if len(text) - last - 1 == 2:
            decimal = ","
        else:
            decimal = None
    elif has_dot:
        decimal = "."
    else:
        decimal = None

    if decimal is None:
        digits = text.replace(",", "").replace(".", "")
        if not digits.isdigit():
            return None
        normalised = digits
    else:
        index = text.rfind(decimal)
        integer_part = text[:index]
        fraction_part = text[index + 1:]
        other = "," if decimal == "." else "."
        integer_part = integer_part.replace(other, "")
        if decimal == ",":
            integer_part = integer_part.replace(",", "")
        elif "." in integer_part:
            # More than one decimal point is ambiguous / invalid.
            return None
        if not integer_part:
            integer_part = "0"
        if not integer_part.isdigit() or not fraction_part.isdigit():
            return None
        normalised = integer_part + "." + fraction_part

    try:
        with localcontext() as context:
            context.prec = max(28, len(normalised) + 2)
            value = Decimal(normalised)
            if negative:
                value = -value
            value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None

    if value == 0:
        value = abs(value)
    return value


def format_amount(value):
    return "{:.2f}".format(value)


def parse_date(raw):
    """Return a YYYY-MM-DD string, or None if the date is invalid."""
    text = raw.strip()
    if not text:
        return None

    match = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
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

    match = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", text)
    if match:
        month = MONTHS.get(match.group(1).lower())
        if month is None:
            return None
        return make_date(int(match.group(3)), month, int(match.group(2)))

    match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text)
    if match:
        month = MONTHS.get(match.group(2).lower())
        if month is None:
            return None
        return make_date(int(match.group(3)), month, int(match.group(1)))

    return None


def make_date(year, month, day):
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def parse_status(raw):
    value = raw.strip().lower()
    if value == "canceled":
        value = "cancelled"
    if value in ALLOWED_STATUSES:
        return value
    return "unknown"


def parse_updated_at(raw):
    """Return a comparable datetime; empty or invalid means oldest possible."""
    text = raw.strip()
    if not text:
        return datetime.min
    match = re.fullmatch(
        r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})Z?", text
    )
    if not match:
        return datetime.min
    try:
        return datetime(*(int(part) for part in match.groups()))
    except ValueError:
        return datetime.min


def parse_currency(raw, amount_raw):
    value = raw.strip().upper()
    if value:
        return SYMBOL_CURRENCIES.get(value, value)

    for symbol, code in SYMBOL_CURRENCIES.items():
        if amount_raw and symbol in amount_raw:
            return code
    return "USD"


def clean(input_path, output_path):
    rows = read_rows(input_path)
    try:
        header = next(rows)
    except StopIteration:
        header = []

    index = {}
    for position, name in enumerate(header):
        normalised = normalise_header(name)
        if normalised in FIELDS and normalised not in index:
            index[normalised] = position

    def cell(row, field):
        position = index.get(field)
        if position is None or position >= len(row):
            return ""
        return row[position]

    kept = {}
    for row in rows:
        order_id = cell(row, "order_id").strip().upper()
        if not order_id:
            continue

        amount_raw = cell(row, "amount")
        amount = parse_amount(amount_raw)
        if amount is None:
            continue

        order_date = parse_date(cell(row, "order_date"))
        if order_date is None:
            continue

        updated_at = parse_updated_at(cell(row, "updated_at"))
        record = {
            "order_id": order_id,
            "customer_email": parse_email(cell(row, "customer_email")),
            "amount": format_amount(amount),
            "currency": parse_currency(cell(row, "currency"), amount_raw),
            "order_date": order_date,
            "status": parse_status(cell(row, "status")),
            "updated_at": updated_at,
        }

        existing = kept.get(order_id)
        if existing is None or updated_at >= existing["updated_at"]:
            kept[order_id] = record

    records = sorted(
        kept.values(), key=lambda item: (item["order_date"], item["order_id"])
    )

    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(OUTPUT_FIELDS)
        for record in records:
            writer.writerow([record[field] for field in OUTPUT_FIELDS])


def main(argv):
    if len(argv) != 3:
        print("Usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2
    clean(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
