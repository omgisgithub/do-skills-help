#!/usr/bin/env python3
"""Clean an order export CSV.

Usage: python3 clean.py INPUT.csv OUTPUT.csv
"""

import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

REQUIRED_COLUMNS = (
    "order_id",
    "customer_email",
    "amount",
    "currency",
    "order_date",
    "status",
    "updated_at",
)

VALID_STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}

SYMBOL_CURRENCY = {"$": "USD", "€": "EUR", "£": "GBP"}

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
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

DATE_HYPHEN_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
DATE_YEAR_SLASH_RE = re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})$")
DATE_MONTH_SLASH_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
DATE_DAY_DOT_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")
DATE_MONTH_FIRST_RE = re.compile(r"^([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})$")
DATE_DAY_FIRST_RE = re.compile(r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$")

AMOUNT_NUMBER_RE = re.compile(r"^(?:\d+(?:\.\d*)?|\.\d+)$")

UPDATED_AT_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})Z?$"
)


def normalize_header(name):
    return name.strip().lower().replace(" ", "_")


def valid_email(value):
    if value.count("@") != 1:
        return ""
    local, domain = value.split("@")
    if not local or not domain:
        return ""
    return value


def parse_amount(raw):
    """Return (formatted_amount, currency_from_symbol) or None if unparseable."""
    original = raw.strip()
    if not original:
        return None

    symbols = [ch for ch in original if ch in SYMBOL_CURRENCY]
    currency = SYMBOL_CURRENCY[symbols[0]] if symbols else None

    text = original
    negative = False

    if "(" in text or ")" in text:
        left = text.find("(")
        right = text.find(")")
        if (
            left == -1
            or right == -1
            or left > right
            or text.count("(") != 1
            or text.count(")") != 1
        ):
            return None
        outside = text[:left] + text[right + 1:]
        if any(ch not in SYMBOL_CURRENCY and not ch.isspace() for ch in outside):
            return None
        negative = True
        text = text[left + 1:right]

    cleaned = "".join(
        ch for ch in text if ch not in SYMBOL_CURRENCY and not ch.isspace()
    )

    if cleaned.startswith("-"):
        negative = not negative
        cleaned = cleaned[1:]
    elif cleaned.startswith("+"):
        cleaned = cleaned[1:]

    if not cleaned or any(ch in "+-()" for ch in cleaned):
        return None

    has_dot = "." in cleaned
    has_comma = "," in cleaned

    if has_dot and has_comma:
        decimal_sep = "." if cleaned.rfind(".") > cleaned.rfind(",") else ","
    elif has_comma:
        tail = cleaned.rsplit(",", 1)[1]
        decimal_sep = "," if len(tail) == 2 and tail.isdigit() else None
    elif has_dot:
        decimal_sep = "."
    else:
        decimal_sep = None

    if decimal_sep == ",":
        head, _, tail = cleaned.rpartition(",")
        core = head.replace(",", "").replace(".", "") + "." + tail
    else:
        core = cleaned.replace(",", "")

    if not AMOUNT_NUMBER_RE.match(core):
        return None

    try:
        value = Decimal(core)
        if negative:
            value = -value
        rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None

    if rounded == 0:
        rounded = abs(rounded)

    return format(rounded, "f"), currency


def parse_date(raw):
    text = raw.strip()
    if not text:
        return None

    match = DATE_HYPHEN_RE.match(text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return safe_date(year, month, day)

    match = DATE_YEAR_SLASH_RE.match(text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return safe_date(year, month, day)

    match = DATE_MONTH_SLASH_RE.match(text)
    if match:
        month, day, year = (int(part) for part in match.groups())
        return safe_date(year, month, day)

    match = DATE_DAY_DOT_RE.match(text)
    if match:
        day, month, year = (int(part) for part in match.groups())
        return safe_date(year, month, day)

    match = DATE_MONTH_FIRST_RE.match(text)
    if match:
        month_name, day, year = match.groups()
        month = MONTHS.get(month_name.lower())
        if month is None:
            return None
        return safe_date(int(year), month, int(day))

    match = DATE_DAY_FIRST_RE.match(text)
    if match:
        day, month_name, year = match.groups()
        month = MONTHS.get(month_name.lower())
        if month is None:
            return None
        return safe_date(int(year), month, int(day))

    return None


def safe_date(year, month, day):
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_updated_at(raw):
    text = raw.strip()
    if not text:
        return datetime.min
    match = UPDATED_AT_RE.match(text)
    if not match:
        return datetime.min
    try:
        return datetime(*(int(part) for part in match.groups()))
    except ValueError:
        return datetime.min


def clean_row(row, index):
    def value(column):
        position = index.get(column)
        if position is None or position >= len(row):
            return ""
        return row[position].strip()

    order_id = value("order_id").upper()
    if not order_id:
        return None

    email = valid_email(value("customer_email").lower())

    amount_result = parse_amount(value("amount"))
    if amount_result is None:
        return None
    amount, symbol_currency = amount_result

    currency = value("currency").upper()
    if currency:
        currency = SYMBOL_CURRENCY.get(currency, currency)
    else:
        currency = symbol_currency or "USD"

    order_date = parse_date(value("order_date"))
    if order_date is None:
        return None

    status = value("status").lower()
    if status == "canceled":
        status = "cancelled"
    if status not in VALID_STATUSES:
        status = "unknown"

    updated_at = parse_updated_at(value("updated_at"))

    return {
        "order_id": order_id,
        "customer_email": email,
        "amount": amount,
        "currency": currency,
        "order_date": order_date,
        "status": status,
        "updated_at": updated_at,
    }


def read_rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        text = handle.read()

    lines = text.splitlines()
    filtered = [
        line
        for line in lines
        if line.strip() != "" and not line.startswith("#")
    ]

    reader = csv.reader(filtered)
    try:
        header = next(reader)
    except StopIteration:
        return []

    normalized = [normalize_header(name) for name in header]
    index = {}
    for position, name in enumerate(normalized):
        if name in REQUIRED_COLUMNS and name not in index:
            index[name] = position

    records = []
    for row in reader:
        record = clean_row(row, index)
        if record is not None:
            records.append(record)
    return records


def deduplicate(records):
    latest = {}
    for record in records:
        key = record["order_id"]
        previous = latest.get(key)
        if previous is None or record["updated_at"] >= previous["updated_at"]:
            latest[key] = record
    return list(latest.values())


def write_rows(path, records):
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
                    record["order_date"].isoformat(),
                    record["status"],
                ]
            )


def main(argv):
    if len(argv) != 3:
        print("usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2

    records = read_rows(argv[1])
    records = deduplicate(records)
    write_rows(argv[2], records)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
