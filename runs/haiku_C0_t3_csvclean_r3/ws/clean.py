#!/usr/bin/env python3
"""Clean a messy order export CSV.

Usage: python3 clean.py INPUT.csv OUTPUT.csv
"""

import csv
import datetime as dt
import re
import sys
from decimal import Decimal, ROUND_HALF_UP

CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
ALLOWED_STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
OUTPUT_HEADER = ["order_id", "customer_email", "amount", "currency", "order_date", "status"]

MONTH_NAMES = ["january", "february", "march", "april", "may", "june", "july",
               "august", "september", "october", "november", "december"]
MONTHS = {}
for number, name in enumerate(MONTH_NAMES, start=1):
    MONTHS[name] = number
    MONTHS[name[:3]] = number

ISO_DATE = re.compile(r"(\d{4})([-/])(\d{1,2})\2(\d{1,2})")   # 2026-03-04, 2026/3/9
DAY_DOT_DATE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")   # 04.03.2026 (day.month.year)
MONTH_DAY_SLASH = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")  # 03/04/2026 (month/day/year)
MONTH_FIRST = re.compile(r"([A-Za-z]+) (\d{1,2}), (\d{4})")   # Mar 4, 2026
DAY_FIRST = re.compile(r"(\d{1,2}) ([A-Za-z]+) (\d{4})")      # 4 Mar 2026

UPDATED_FORMATS = ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S")


def parse_date(raw):
    text = re.sub(r"\s+", " ", raw.strip())
    year = month = day = None
    match = ISO_DATE.fullmatch(text)
    if match:
        year, month, day = int(match[1]), int(match[3]), int(match[4])
    elif match := DAY_DOT_DATE.fullmatch(text):
        day, month, year = int(match[1]), int(match[2]), int(match[3])
    elif match := MONTH_DAY_SLASH.fullmatch(text):
        month, day, year = int(match[1]), int(match[2]), int(match[3])
    elif match := MONTH_FIRST.fullmatch(text):
        month, day, year = MONTHS.get(match[1].lower()), int(match[2]), int(match[3])
    elif match := DAY_FIRST.fullmatch(text):
        day, month, year = int(match[1]), MONTHS.get(match[2].lower()), int(match[3])
    if month is None:
        return None
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


def normalise_number(text):
    """Turn '1.234,56' / '1,234.56' / '1,000' / '7,5' into plain '1234.56' style text."""
    has_dot, has_comma = "." in text, "," in text
    if has_dot and has_comma:
        decimal = "." if text.rfind(".") > text.rfind(",") else ","
    elif has_comma:
        tail = text[text.rfind(",") + 1:]
        decimal = "," if re.fullmatch(r"\d{2}", tail) else None
    elif has_dot:
        decimal = "."
    else:
        decimal = None

    if decimal == ".":
        return text.replace(",", "")
    if decimal == ",":
        head, _, tail = text.rpartition(",")
        return head.replace(",", "").replace(".", "") + "." + tail
    return text.replace(",", "")


def parse_amount(raw):
    """Return (Decimal, currency implied by a symbol or None), or None if unparseable."""
    symbol_currency = None
    for ch in raw:
        if ch in CURRENCY_SYMBOLS:
            symbol_currency = CURRENCY_SYMBOLS[ch]
            break
    negative = "(" in raw or "-" in raw
    text = re.sub(r"[\s$€£()\-]", "", raw)
    if not text:
        return None
    text = normalise_number(text)
    if not re.fullmatch(r"\d*\.?\d+", text):
        return None
    value = Decimal(text)
    return (-value if negative else value), symbol_currency


def format_amount(value):
    rounded = abs(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if value < 0 and rounded != 0:
        rounded = -rounded
    return f"{rounded:.2f}"


def clean_email(raw):
    email = raw.strip().lower()
    local, sep, domain = email.partition("@")
    if not sep or "@" in domain or not local.strip() or not domain.strip():
        return ""
    return email


def clean_status(raw):
    status = raw.strip().lower()
    if status == "canceled":
        status = "cancelled"
    return status if status in ALLOWED_STATUSES else "unknown"


def parse_updated(raw):
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1]
    for fmt in UPDATED_FORMATS:
        try:
            return dt.datetime.strptime(text, fmt)
        except ValueError:
            pass
    return dt.datetime.min


def clean_record(get):
    """Return a cleaned row dict, or None if the row must be dropped."""
    order_id = get("order_id").strip().upper()
    if not order_id:
        return None

    parsed_amount = parse_amount(get("amount"))
    if parsed_amount is None:
        return None
    amount, symbol_currency = parsed_amount

    order_date = parse_date(get("order_date"))
    if order_date is None:
        return None

    currency = get("currency").strip().upper()
    currency = CURRENCY_SYMBOLS.get(currency, currency)
    if not currency:
        currency = symbol_currency or "USD"

    return {
        "order_id": order_id,
        "customer_email": clean_email(get("customer_email")),
        "amount": format_amount(amount),
        "currency": currency,
        "order_date": order_date.isoformat(),
        "status": clean_status(get("status")),
        "updated_at": parse_updated(get("updated_at")),
    }


def read_records(path):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        lines = [line for line in handle if line.strip() and not line.startswith("#")]
    rows = [row for row in csv.reader(lines) if any(cell.strip() for cell in row)]
    if not rows:
        return []

    header = [name.strip().lower().replace(" ", "_") for name in rows[0]]
    index = {}
    for position, name in enumerate(header):
        index.setdefault(name, position)

    records = []
    for row in rows[1:]:
        def get(name, row=row):
            position = index.get(name)
            if position is None or position >= len(row):
                return ""
            return row[position]
        record = clean_record(get)
        if record is not None:
            records.append(record)
    return records


def deduplicate(records):
    latest = {}
    for record in records:
        current = latest.get(record["order_id"])
        # Ties go to the later row in the file, hence >=.
        if current is None or record["updated_at"] >= current["updated_at"]:
            latest[record["order_id"]] = record
    return sorted(latest.values(), key=lambda r: (r["order_date"], r["order_id"]))


def main(argv):
    if len(argv) != 3:
        print("usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2
    rows = deduplicate(read_records(argv[1]))
    with open(argv[2], "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(OUTPUT_HEADER)
        for row in rows:
            writer.writerow([row[name] for name in OUTPUT_HEADER])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
