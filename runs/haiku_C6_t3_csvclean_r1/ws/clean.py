#!/usr/bin/env python3
"""Clean a messy order export CSV.

Usage: python3 clean.py INPUT.csv OUTPUT.csv
"""

import csv
import re
import sys
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

OUT_HEADER = ["order_id", "customer_email", "amount", "currency", "order_date", "status"]
CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "september": 9, "oct": 10, "october": 10,
    "nov": 11, "november": 11, "dec": 12, "december": 12,
}

# One strict pattern per accepted date form; groups are named by role.
DATE_PATTERNS = [
    (re.compile(r"([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})"), ("y", "m", "d")),
    (re.compile(r"([0-9]{4})/([0-9]{1,2})/([0-9]{1,2})"), ("y", "m", "d")),
    (re.compile(r"([0-9]{1,2})\.([0-9]{1,2})\.([0-9]{4})"), ("d", "m", "y")),
    (re.compile(r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})"), ("m", "d", "y")),
    (re.compile(r"([A-Za-z]+) ([0-9]{1,2}), ([0-9]{4})"), ("mon", "d", "y")),
    (re.compile(r"([0-9]{1,2}) ([A-Za-z]+) ([0-9]{4})"), ("d", "mon", "y")),
]

UPDATED_RE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})[T ]([0-9]{2}):([0-9]{2}):([0-9]{2})Z?")
AMOUNT_RE = re.compile(r"[0-9]*\.?[0-9]+")


def field(row, index, name):
    i = index.get(name)
    if i is None or i >= len(row):
        return ""
    return row[i].strip()


def parse_amount(text):
    """Return (amount as Decimal, currency symbol or None), or None if unparseable."""
    symbol = next((c for c in text if c in CURRENCY_SYMBOLS), None)
    s = "".join(c for c in text if not c.isspace() and c not in CURRENCY_SYMBOLS)

    negative = s.startswith("(") and s.endswith(")")
    if negative:
        s = s[1:-1]

    if "," in s and "." not in s:
        head, _, tail = s.rpartition(",")
        if re.fullmatch(r"[0-9]{2}", tail):
            s = head.replace(",", "") + "." + tail
        else:
            s = s.replace(",", "")
    elif "," in s and "." in s:
        decimal = "." if s.rfind(".") > s.rfind(",") else ","
        thousands = "," if decimal == "." else "."
        s = s.replace(thousands, "").replace(decimal, ".")

    if not AMOUNT_RE.fullmatch(s):
        return None

    value = Decimal(s)
    if negative:
        value = -value
    try:
        value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None
    if value == 0:
        value = Decimal("0.00")
    return value, symbol


def parse_date(text):
    for pattern, roles in DATE_PATTERNS:
        m = pattern.fullmatch(text)
        if not m:
            continue
        parts = dict(zip(roles, m.groups()))
        if "mon" in parts:
            month = MONTHS.get(parts["mon"].lower())
        else:
            month = int(parts["m"])
        if month is None:
            return None
        try:
            return date(int(parts["y"]), month, int(parts["d"]))
        except ValueError:
            return None
    return None


def parse_updated(text):
    """Empty or unparseable values sort as the oldest possible time."""
    m = UPDATED_RE.fullmatch(text)
    if not m:
        return datetime.min
    try:
        return datetime(*(int(g) for g in m.groups()))
    except ValueError:
        return datetime.min


def normalise_currency(text, amount_symbol):
    if text:
        return CURRENCY_SYMBOLS.get(text, text.upper())
    return CURRENCY_SYMBOLS.get(amount_symbol, "USD")


def normalise_email(text):
    s = text.strip().lower()
    local, sep, domain = s.partition("@")
    if sep and local and domain and "@" not in domain:
        return s
    return ""


def normalise_status(text):
    s = text.strip().lower()
    if s == "canceled":
        s = "cancelled"
    return s if s in STATUSES else "unknown"


def read_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        lines = [line for line in f if line.strip() and not line.startswith("#")]
    return list(csv.reader(lines))


def clean(path):
    rows = read_rows(path)
    if not rows:
        return []
    header = [name.strip().lower().replace(" ", "_") for name in rows[0]]
    index = {}
    for i, name in enumerate(header):
        index.setdefault(name, i)

    best = {}
    for position, row in enumerate(rows[1:]):
        order_id = field(row, index, "order_id").upper()
        if not order_id:
            continue
        parsed = parse_amount(field(row, index, "amount"))
        if parsed is None:
            continue
        amount, amount_symbol = parsed
        order_date = parse_date(field(row, index, "order_date"))
        if order_date is None:
            continue

        record = (
            order_id,
            normalise_email(field(row, index, "customer_email")),
            f"{amount:.2f}",
            normalise_currency(field(row, index, "currency").upper(), amount_symbol),
            order_date.isoformat(),
            normalise_status(field(row, index, "status")),
        )
        key = (parse_updated(field(row, index, "updated_at")), position)
        if order_id not in best or key > best[order_id][0]:
            best[order_id] = (key, record)

    return sorted((record for _, record in best.values()), key=lambda r: (r[4], r[0]))


def write(path, records):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(OUT_HEADER)
        writer.writerows(records)


def main(argv):
    if len(argv) != 3:
        print("usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2
    write(argv[2], clean(argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
