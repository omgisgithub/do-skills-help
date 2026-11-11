#!/usr/bin/env python3
"""Clean a messy order export: python3 clean.py INPUT.csv OUTPUT.csv"""

import csv
import datetime
import re
import sys
from decimal import Decimal, ROUND_HALF_UP

OUTPUT_HEADER = ["order_id", "customer_email", "amount", "currency", "order_date", "status"]
ALLOWED_STATUS = {"pending", "paid", "shipped", "cancelled", "refunded"}
SYMBOL_CURRENCY = {"$": "USD", "€": "EUR", "£": "GBP"}
OLDEST = datetime.datetime.min

MONTH_NUMBERS = {}
for _number, _name in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1):
    MONTH_NUMBERS[_name] = _number
    MONTH_NUMBERS[_name[:3]] = _number

# Each accepted date form, with the meaning of its regex groups.
DATE_FORMS = (
    (re.compile(r"([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})"), ("y", "m", "d")),     # 2026-03-04
    (re.compile(r"([0-9]{4})/([0-9]{1,2})/([0-9]{1,2})"), ("y", "m", "d")),     # 2026/03/04
    (re.compile(r"([0-9]{1,2})\.([0-9]{1,2})\.([0-9]{4})"), ("d", "m", "y")),   # 04.03.2026
    (re.compile(r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})"), ("m", "d", "y")),     # 03/04/2026
    (re.compile(r"([A-Za-z]+) ([0-9]{1,2}), ([0-9]{4})"), ("mon", "d", "y")),   # Mar 4, 2026
    (re.compile(r"([0-9]{1,2}) ([A-Za-z]+) ([0-9]{4})"), ("d", "mon", "y")),    # 4 Mar 2026
)

# A plain number after separators are resolved: digits with at most one decimal point.
PLAIN_NUMBER_RE = re.compile(r"[0-9]*\.?[0-9]+")
TWO_DIGITS_RE = re.compile(r"[0-9]{2}")
UPDATED_AT_RE = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})[T ]([0-9]{2}):([0-9]{2}):([0-9]{2})Z?")


def parse_amount(raw):
    """Return (Decimal, currency symbol or None), or None if the amount is unusable."""
    symbol = next((ch for ch in raw if ch in SYMBOL_CURRENCY), None)
    text = "".join(ch for ch in raw if ch not in SYMBOL_CURRENCY and not ch.isspace())

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    elif text.startswith("-"):
        negative = True
        text = text[1:]

    has_dot, has_comma = "." in text, "," in text
    if has_dot and has_comma:
        decimal = "." if text.rfind(".") > text.rfind(",") else ","
    elif has_comma:
        tail = text[text.rfind(",") + 1:]
        decimal = "," if TWO_DIGITS_RE.fullmatch(tail) else None
    elif has_dot:
        decimal = "."
    else:
        decimal = None

    if decimal == ",":
        normalized = text.replace(".", "").replace(",", ".")
    else:
        normalized = text.replace(",", "")

    if PLAIN_NUMBER_RE.fullmatch(normalized) is None:
        return None
    value = Decimal(normalized)
    if negative:
        value = -value
    return value, symbol


def format_amount(value):
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if rounded == 0:
        rounded = abs(rounded)
    return f"{rounded:.2f}"


def parse_date(raw):
    text = raw.strip()
    for pattern, order in DATE_FORMS:
        match = pattern.fullmatch(text)
        if match is None:
            continue
        parts = dict(zip(order, match.groups()))
        if "mon" in parts:
            month = MONTH_NUMBERS.get(parts["mon"].lower())
        else:
            month = int(parts["m"])
        if month is None:
            return None
        try:
            return datetime.date(int(parts["y"]), month, int(parts["d"])).isoformat()
        except ValueError:
            return None
    return None


def parse_updated_at(raw):
    match = UPDATED_AT_RE.fullmatch(raw.strip())
    if match is None:
        return OLDEST
    try:
        return datetime.datetime(*(int(part) for part in match.groups()))
    except ValueError:
        return OLDEST


def clean_email(raw):
    text = raw.strip().lower()
    local, separator, domain = text.partition("@")
    if separator and local and domain and "@" not in domain:
        return text
    return ""


def clean_currency(raw, symbol):
    text = raw.strip().upper()
    if not text:
        return SYMBOL_CURRENCY.get(symbol, "USD")
    return SYMBOL_CURRENCY.get(text, text)


def clean_status(raw):
    text = raw.strip().lower()
    if text == "canceled":
        text = "cancelled"
    return text if text in ALLOWED_STATUS else "unknown"


def read_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        lines = [line for line in f if line.strip() and not line.startswith("#")]
    return list(csv.reader(lines))


def header_index(header):
    index = {}
    for position, name in enumerate(header):
        key = name.strip().lower().replace(" ", "_")
        index.setdefault(key, position)
    return index


def field(row, index, name):
    position = index.get(name)
    if position is None or position >= len(row):
        return ""
    return row[position]


def clean_rows(rows):
    if not rows:
        return []
    index = header_index(rows[0])

    latest = {}  # order_id -> (sort key, record)
    for position, row in enumerate(rows[1:]):
        order_id = field(row, index, "order_id").strip().upper()
        if not order_id:
            continue
        parsed = parse_amount(field(row, index, "amount"))
        if parsed is None:
            continue
        amount, symbol = parsed
        order_date = parse_date(field(row, index, "order_date"))
        if order_date is None:
            continue

        record = {
            "order_id": order_id,
            "customer_email": clean_email(field(row, index, "customer_email")),
            "amount": format_amount(amount),
            "currency": clean_currency(field(row, index, "currency"), symbol),
            "order_date": order_date,
            "status": clean_status(field(row, index, "status")),
        }
        key = (parse_updated_at(field(row, index, "updated_at")), position)
        current = latest.get(order_id)
        if current is None or key > current[0]:
            latest[order_id] = (key, record)

    records = [record for _, record in latest.values()]
    records.sort(key=lambda r: (r["order_date"], r["order_id"]))
    return records


def write_csv(path, records):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(OUTPUT_HEADER)
        for r in records:
            writer.writerow([r[name] for name in OUTPUT_HEADER])


def main(argv):
    if len(argv) != 3:
        print("usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2
    write_csv(argv[2], clean_rows(read_rows(argv[1])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
