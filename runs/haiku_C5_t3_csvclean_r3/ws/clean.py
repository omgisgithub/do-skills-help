#!/usr/bin/env python3
"""Clean a messy order export.

Usage: python3 clean.py INPUT.csv OUTPUT.csv
"""

import csv
import datetime as dt
import re
import sys
from decimal import ROUND_HALF_UP, Decimal

OUTPUT_COLUMNS = ["order_id", "customer_email", "amount", "currency", "order_date", "status"]
INPUT_COLUMNS = OUTPUT_COLUMNS + ["updated_at"]
ALLOWED_STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}

MONTHS = {}
for number, name in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1):
    MONTHS[name] = number
    MONTHS[name[:3]] = number

ISO_LIKE_DATE = re.compile(r"([0-9]{4})([-/])([0-9]{1,2})\2([0-9]{1,2})")
DAY_FIRST_DATE = re.compile(r"([0-9]{1,2})\.([0-9]{1,2})\.([0-9]{4})")
MONTH_FIRST_DATE = re.compile(r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})")
MONTH_NAME_FIRST = re.compile(r"([a-z]+)\.?\s+([0-9]{1,2}),\s*([0-9]{4})")
DAY_FIRST_MONTH_NAME = re.compile(r"([0-9]{1,2})\s+([a-z]+)\.?\s+([0-9]{4})")
UPDATED_AT = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})[T ]([0-9]{2}):([0-9]{2}):([0-9]{2})Z?")


def read_rows(path):
    """Yield each data row as a dict keyed by the normalised column names."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        # Blank lines and comment lines are skipped before CSV parsing.
        lines = [line for line in f if line.strip() and not line.startswith("#")]

    reader = csv.reader(lines)
    header = next(reader, [])
    index = {}
    for position, name in enumerate(h.strip().lower().replace(" ", "_") for h in header):
        index.setdefault(name, position)

    for values in reader:
        row = {}
        for column in INPUT_COLUMNS:
            position = index.get(column)
            if position is not None and position < len(values):
                row[column] = values[position].strip()
            else:
                row[column] = ""
        yield row


def parse_amount(text):
    """Return (Decimal rounded to cents, currency symbol or None), or None if unparseable."""
    s = text.strip()
    if ("(" in s) != (")" in s):
        return None
    negative = "-" in s or "(" in s

    symbol = next((ch for ch in s if ch in CURRENCY_SYMBOLS), None)
    body = re.sub(r"[\s$€£()\-]", "", s)
    if not re.fullmatch(r"[0-9.,]+", body):
        return None

    if "." in body and "," in body:
        decimal = "." if body.rfind(".") > body.rfind(",") else ","
    elif "," in body:
        decimal = "," if len(body.rsplit(",", 1)[1]) == 2 else None
    elif "." in body:
        decimal = "."
    else:
        decimal = None

    if decimal:
        whole, _, fraction = body.rpartition(decimal)
    else:
        whole, fraction = body, ""
    whole = whole.replace(",", "")
    if decimal == ",":
        whole = whole.replace(".", "")
    if not re.fullmatch(r"[0-9]*", whole) or not re.fullmatch(r"[0-9]*", fraction):
        return None
    if not whole and not fraction:
        return None

    value = Decimal(f"{whole or '0'}.{fraction or '0'}")
    if negative:
        value = -value
    cents = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if cents == 0:
        cents = Decimal("0.00")
    return cents, symbol


def parse_date(text):
    """Return the date as YYYY-MM-DD, or None if it is missing or invalid."""
    s = text.strip().lower()
    year = month = day = None
    if match := ISO_LIKE_DATE.fullmatch(s):
        year, month, day = match.group(1), match.group(3), match.group(4)
    elif match := DAY_FIRST_DATE.fullmatch(s):
        day, month, year = match.groups()
    elif match := MONTH_FIRST_DATE.fullmatch(s):
        month, day, year = match.groups()
    elif match := MONTH_NAME_FIRST.fullmatch(s):
        month, day, year = MONTHS.get(match.group(1)), match.group(2), match.group(3)
    elif match := DAY_FIRST_MONTH_NAME.fullmatch(s):
        day, month, year = match.group(1), MONTHS.get(match.group(2)), match.group(3)
    if month is None:
        return None
    try:
        return dt.date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def parse_updated_at(text):
    """Return a datetime for ordering; missing or invalid values are the oldest possible."""
    match = UPDATED_AT.fullmatch(text.strip())
    if not match:
        return dt.datetime.min
    try:
        return dt.datetime(*(int(part) for part in match.groups()))
    except ValueError:
        return dt.datetime.min


def normalise_currency(text):
    s = text.strip()
    return CURRENCY_SYMBOLS.get(s, s.upper())


def normalise_email(text):
    local, separator, domain = text.strip().lower().partition("@")
    if separator and local and domain and "@" not in domain:
        return f"{local}@{domain}"
    return ""


def normalise_status(text):
    s = text.strip().lower()
    if s == "canceled":
        s = "cancelled"
    return s if s in ALLOWED_STATUSES else "unknown"


def clean_row(row):
    """Return (output row, updated_at) or None if the row must be dropped."""
    order_id = row["order_id"].upper()
    if not order_id:
        return None

    parsed = parse_amount(row["amount"])
    if parsed is None:
        return None
    amount, amount_symbol = parsed

    order_date = parse_date(row["order_date"])
    if order_date is None:
        return None

    if row["currency"]:
        currency = normalise_currency(row["currency"])
    elif amount_symbol:
        currency = CURRENCY_SYMBOLS[amount_symbol]
    else:
        currency = "USD"

    output = {
        "order_id": order_id,
        "customer_email": normalise_email(row["customer_email"]),
        "amount": f"{amount:f}",
        "currency": currency,
        "order_date": order_date,
        "status": normalise_status(row["status"]),
    }
    return output, parse_updated_at(row["updated_at"])


def clean(rows):
    """Return the cleaned rows, de-duplicated and sorted."""
    latest = {}
    for position, row in enumerate(rows):
        cleaned = clean_row(row)
        if cleaned is None:
            continue
        output, updated_at = cleaned
        # The file position breaks ties, so a later row wins over an earlier one.
        key = (updated_at, position)
        order_id = output["order_id"]
        if order_id not in latest or key > latest[order_id][0]:
            latest[order_id] = (key, output)

    kept = [output for _, output in latest.values()]
    kept.sort(key=lambda r: (r["order_date"], r["order_id"]))
    return kept


def main(argv):
    if len(argv) != 3:
        print("usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2

    rows = clean(read_rows(argv[1]))
    with open(argv[2], "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(OUTPUT_COLUMNS)
        for row in rows:
            writer.writerow([row[column] for column in OUTPUT_COLUMNS])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
