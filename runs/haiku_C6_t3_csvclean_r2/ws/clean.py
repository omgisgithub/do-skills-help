#!/usr/bin/env python3
"""Clean a messy order export CSV.

Usage: python3 clean.py INPUT.csv OUTPUT.csv
"""

import csv
import datetime
import decimal
import re
import sys

OUTPUT_COLUMNS = ["order_id", "customer_email", "amount", "currency", "order_date", "status"]
ALLOWED_STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
SYMBOL_CURRENCIES = {"$": "USD", "€": "EUR", "£": "GBP"}
MONTH_NAMES = ["january", "february", "march", "april", "may", "june",
               "july", "august", "september", "october", "november", "december"]
MONTHS = {}
for number, name in enumerate(MONTH_NAMES, 1):
    MONTHS[name] = number
    MONTHS[name[:3]] = number

AMOUNT_BODY = re.compile(r"[0-9.,]+")
TWO_DIGITS = re.compile(r"[0-9]{2}")
UPDATED_AT = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})[T ]([0-9]{2}):([0-9]{2}):([0-9]{2})Z?")

# Each pattern lists what its groups mean: y/m/d are numbers, M is an English month name.
DATE_PATTERNS = [
    (re.compile(r"([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})"), ("y", "m", "d")),
    (re.compile(r"([0-9]{4})/([0-9]{1,2})/([0-9]{1,2})"), ("y", "m", "d")),
    (re.compile(r"([0-9]{1,2})\.([0-9]{1,2})\.([0-9]{4})"), ("d", "m", "y")),
    (re.compile(r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})"), ("m", "d", "y")),
    (re.compile(r"([A-Za-z]+) ([0-9]{1,2}), ([0-9]{4})"), ("M", "d", "y")),
    (re.compile(r"([0-9]{1,2}) ([A-Za-z]+) ([0-9]{4})"), ("d", "M", "y")),
]


def parse_amount(text):
    """Return (Decimal, first currency symbol or None), or None if the amount is invalid."""
    symbol = None
    chars = []
    for char in text:
        if char.isspace():
            continue
        if char in SYMBOL_CURRENCIES:
            symbol = symbol or char
        else:
            chars.append(char)
    body = "".join(chars)

    negative = body.startswith("(") and body.endswith(")")
    if negative:
        body = body[1:-1]
    if not AMOUNT_BODY.fullmatch(body) or not re.search("[0-9]", body):
        return None

    if "." in body and "," in body:
        sep = "." if body.rfind(".") > body.rfind(",") else ","
    elif "," in body:
        sep = "," if TWO_DIGITS.fullmatch(body[body.rfind(",") + 1:]) else None
    elif "." in body:
        sep = "."
    else:
        sep = None

    if sep:
        whole, _, fraction = body.rpartition(sep)
    else:
        whole, fraction = body, ""
    if sep == "." and "." in whole:
        return None  # only one decimal point is allowed
    whole = whole.replace(",", "").replace(".", "")
    if not whole and not fraction:
        return None

    try:
        value = decimal.Decimal(f"{whole or '0'}.{fraction or '0'}")
        if negative:
            value = -value
        value = value.quantize(decimal.Decimal("0.01"), rounding=decimal.ROUND_HALF_UP)
    except decimal.InvalidOperation:
        return None
    if value == 0:
        value = decimal.Decimal("0.00")
    return value, symbol


def parse_date(text):
    """Return a datetime.date for one of the accepted forms, or None."""
    value = text.strip()
    for pattern, fields in DATE_PATTERNS:
        match = pattern.fullmatch(value)
        if match:
            break
    else:
        return None

    parts = dict(zip(fields, match.groups()))
    if "M" in parts:
        month = MONTHS.get(parts["M"].lower())
    else:
        month = int(parts["m"])
    if month is None:
        return None
    try:
        return datetime.date(int(parts["y"]), month, int(parts["d"]))
    except ValueError:
        return None


def parse_updated_at(text):
    """Return a datetime for de-duplication; empty or invalid means the oldest possible."""
    match = UPDATED_AT.fullmatch(text.strip())
    if not match:
        return datetime.datetime.min
    try:
        return datetime.datetime(*map(int, match.groups()))
    except ValueError:
        return datetime.datetime.min


def clean_email(text):
    value = text.strip().lower()
    local, sep, domain = value.partition("@")
    if sep and "@" not in domain and local.strip() and domain.strip():
        return value
    return ""


def clean_currency(text, symbol):
    value = text.strip().upper()
    if not value:
        return SYMBOL_CURRENCIES.get(symbol, "USD")
    return SYMBOL_CURRENCIES.get(value, value)


def clean_status(text):
    value = text.strip().lower()
    if value == "canceled":
        value = "cancelled"
    return value if value in ALLOWED_STATUSES else "unknown"


def clean(source, target):
    with open(source, newline="", encoding="utf-8-sig") as handle:
        lines = [line for line in handle if line.strip() and not line.startswith("#")]
    reader = csv.reader(lines)

    header = next(reader, [])
    columns = {}
    for position, name in enumerate(header):
        columns.setdefault(name.strip().lower().replace(" ", "_"), position)

    def field(row, name):
        position = columns.get(name)
        return row[position] if position is not None and position < len(row) else ""

    # order_id -> (de-duplication key, record)
    best = {}
    for number, row in enumerate(reader):
        order_id = field(row, "order_id").strip().upper()
        if not order_id:
            continue
        amount = parse_amount(field(row, "amount"))
        if amount is None:
            continue
        order_date = parse_date(field(row, "order_date"))
        if order_date is None:
            continue

        value, symbol = amount
        record = {
            "order_id": order_id,
            "customer_email": clean_email(field(row, "customer_email")),
            "amount": f"{value:.2f}",
            "currency": clean_currency(field(row, "currency"), symbol),
            "order_date": order_date.isoformat(),
            "status": clean_status(field(row, "status")),
        }
        key = (parse_updated_at(field(row, "updated_at")), number)
        if order_id not in best or key > best[order_id][0]:
            best[order_id] = (key, record)

    records = sorted((record for _, record in best.values()),
                     key=lambda record: (record["order_date"], record["order_id"]))
    with open(target, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(OUTPUT_COLUMNS)
        for record in records:
            writer.writerow([record[column] for column in OUTPUT_COLUMNS])


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python3 clean.py INPUT.csv OUTPUT.csv")
    clean(sys.argv[1], sys.argv[2])
