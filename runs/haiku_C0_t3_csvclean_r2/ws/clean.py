#!/usr/bin/env python3
"""Clean a messy order export CSV.

Usage: python3 clean.py INPUT.csv OUTPUT.csv
"""

import csv
import re
import sys
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

OUTPUT_HEADER = ["order_id", "customer_email", "amount", "currency", "order_date", "status"]
ALLOWED_STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
MONTHS = {
    name.lower(): number
    for number, names in enumerate(
        [
            ("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"),
            ("may", "may"), ("june", "jun"), ("july", "jul"), ("august", "aug"),
            ("september", "sep"), ("october", "oct"), ("november", "nov"), ("december", "dec"),
        ],
        start=1,
    )
    for name in names
}


def read_rows(path):
    # utf-8-sig drops a leading BOM; newline="" lets csv handle quoted line breaks.
    with open(path, newline="", encoding="utf-8-sig") as f:
        lines = [line for line in f if line.strip() and not line.startswith("#")]
    return list(csv.reader(lines))


def normalise_header(name):
    return name.strip().lower().replace(" ", "_")


def clean_email(raw):
    value = raw.strip().lower()
    local, sep, domain = value.partition("@")
    if sep and local and domain and "@" not in domain:
        return value
    return ""


def parse_amount(raw):
    """Return the amount as a Decimal rounded to 2 places, or None if unparseable."""
    s = re.sub(r"[\s$€£]", "", raw)
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative, s = True, s[1:-1]
    elif s.startswith("-"):
        negative, s = True, s[1:]

    last_dot, last_comma = s.rfind("."), s.rfind(",")
    if last_dot >= 0 and last_comma >= 0:
        decimal = "." if last_dot > last_comma else ","
    elif last_comma >= 0:
        decimal = "," if len(s) - last_comma - 1 == 2 else None
    elif last_dot >= 0:
        decimal = "."
    else:
        decimal = None

    if decimal == ",":
        s = s[:last_comma].replace(".", "").replace(",", "") + "." + s[last_comma + 1:]
    else:
        s = s.replace(",", "")

    if not re.search(r"\d", s) or not re.fullmatch(r"\d*\.?\d*", s):
        return None
    try:
        value = Decimal(s).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None
    if negative:
        value = -value
    return value + 0  # turns -0.00 into 0.00


def currency_from_symbol(raw):
    for char, code in CURRENCY_SYMBOLS.items():
        if char in raw:
            return code
    return None


def clean_currency(raw_currency, raw_amount):
    value = raw_currency.strip()
    if value:
        return CURRENCY_SYMBOLS.get(value, value.upper())
    return currency_from_symbol(raw_amount) or "USD"


def _iso(year, month, day):
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def parse_date(raw):
    """Return the date as YYYY-MM-DD, or None if missing or invalid."""
    s = re.sub(r"\s+", " ", raw.strip())

    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        return _iso(m.group(1), m.group(2), m.group(3))

    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)  # day.month.year
    if m:
        return _iso(m.group(3), m.group(2), m.group(1))

    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)  # month/day/year
    if m:
        return _iso(m.group(3), m.group(1), m.group(2))

    m = re.fullmatch(r"([A-Za-z]+)\.? (\d{1,2}),? (\d{4})", s)  # Mar 4, 2026
    if m and m.group(1).lower() in MONTHS:
        return _iso(m.group(3), MONTHS[m.group(1).lower()], m.group(2))

    m = re.fullmatch(r"(\d{1,2}) ([A-Za-z]+),? (\d{4})", s)  # 4 Mar 2026
    if m and m.group(2).lower() in MONTHS:
        return _iso(m.group(3), MONTHS[m.group(2).lower()], m.group(1))

    return None


def clean_status(raw):
    value = raw.strip().lower()
    if value == "canceled":
        value = "cancelled"
    return value if value in ALLOWED_STATUSES else "unknown"


def parse_updated(raw):
    """Return the timestamp as a naive datetime, or None if empty or invalid."""
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})Z?", raw.strip())
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + " " + m.group(2), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def field(row, index, name):
    i = index.get(name)
    return row[i] if i is not None and i < len(row) else ""


def clean(rows):
    if not rows:
        return []
    index = {}
    for i, name in enumerate(normalise_header(h) for h in rows[0]):
        index.setdefault(name, i)

    latest = {}  # order_id -> (sort key, cleaned row)
    for position, row in enumerate(rows[1:]):
        order_id = field(row, index, "order_id").strip().upper()
        if not order_id:
            continue
        raw_amount = field(row, index, "amount")
        amount = parse_amount(raw_amount)
        if amount is None:
            continue
        order_date = parse_date(field(row, index, "order_date"))
        if order_date is None:
            continue

        out = {
            "order_id": order_id,
            "customer_email": clean_email(field(row, index, "customer_email")),
            "amount": f"{amount:.2f}",
            "currency": clean_currency(field(row, index, "currency"), raw_amount),
            "order_date": order_date,
            "status": clean_status(field(row, index, "status")),
        }
        # Oldest possible when updated_at is empty or unparseable; later rows win ties.
        key = (parse_updated(field(row, index, "updated_at")) or datetime.min, position)
        if order_id not in latest or key > latest[order_id][0]:
            latest[order_id] = (key, out)

    records = [out for _, out in latest.values()]
    records.sort(key=lambda r: (r["order_date"], r["order_id"]))
    return records


def write(path, records):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: python3 clean.py INPUT.csv OUTPUT.csv")
    write(sys.argv[2], clean(read_rows(sys.argv[1])))


if __name__ == "__main__":
    main()
