#!/usr/bin/env python3
"""Clean a messy order export CSV.

Usage: python3 clean.py INPUT.csv OUTPUT.csv
"""
import calendar
import csv
import datetime as dt
import re
import sys
from decimal import ROUND_HALF_UP, Decimal

OUTPUT_FIELDS = ["order_id", "customer_email", "amount", "currency", "order_date", "status"]
ALLOWED_STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}

MONTHS = {}
for _month in range(1, 13):
    MONTHS[calendar.month_name[_month].lower()] = _month
    MONTHS[calendar.month_abbr[_month].lower()] = _month

# (pattern, meaning of each group). "name" is an English month name.
DATE_FORMATS = [
    (r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", ("y", "m", "d")),       # 2026-03-04, 2026/3/9
    (r"(\d{1,2})\.(\d{1,2})\.(\d{4})", ("d", "m", "y")),           # 04.03.2026
    (r"(\d{1,2})/(\d{1,2})/(\d{4})", ("m", "d", "y")),             # 03/04/2026
    (r"([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})", ("name", "d", "y")),  # Mar 4, 2026
    (r"(\d{1,2})\s+([A-Za-z]+)\.?,?\s+(\d{4})", ("d", "name", "y")),  # 4 Mar 2026
]


def parse_amount(text):
    """Return the amount as a string with 2 decimals, or None if it cannot be parsed."""
    negative = "-" in text or ("(" in text and ")" in text)
    digits = re.sub(r"[\s$€£()\-]", "", text)

    if "." in digits and "," in digits:
        # Whichever separator comes last is the decimal one.
        if digits.rfind(",") > digits.rfind("."):
            digits = digits.replace(".", "").replace(",", ".")
        else:
            digits = digits.replace(",", "")
    elif "," in digits:
        head, _, tail = digits.rpartition(",")
        if re.fullmatch(r"\d{2}", tail):
            digits = head.replace(",", "") + "." + tail
        else:
            digits = digits.replace(",", "")

    if not re.search(r"\d", digits) or not re.fullmatch(r"\d*\.?\d*", digits):
        return None

    value = Decimal(digits)
    if negative:
        value = -value
    value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if value == 0:
        value = Decimal("0.00")  # avoid "-0.00"
    return format(value, ".2f")


def parse_date(text):
    """Return the date as YYYY-MM-DD, or None if it is missing or invalid."""
    text = text.strip()
    for pattern, keys in DATE_FORMATS:
        match = re.fullmatch(pattern, text)
        if not match:
            continue
        parts = dict(zip(keys, match.groups()))
        if "name" in parts:
            month = MONTHS.get(parts["name"].lower())
        else:
            month = int(parts["m"])
        if month is None:
            return None
        try:
            return dt.date(int(parts["y"]), month, int(parts["d"])).isoformat()
        except ValueError:
            return None
    return None


def parse_updated_at(text):
    """Return a datetime, or None when empty or unparseable (treated as oldest)."""
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})Z?", text.strip())
    if not match:
        return None
    try:
        return dt.datetime.strptime(match.group(1) + " " + match.group(2), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def clean_email(text):
    email = text.strip().lower()
    local, sep, domain = email.partition("@")
    if sep and local and domain and "@" not in domain:
        return email
    return ""


def clean_currency(text, amount_text):
    code = text.strip()
    if not code:
        code = next((CURRENCY_SYMBOLS[c] for c in amount_text if c in CURRENCY_SYMBOLS), "USD")
    return CURRENCY_SYMBOLS.get(code, code.upper())


def clean_status(text):
    status = text.strip().lower()
    if status == "canceled":
        status = "cancelled"
    return status if status in ALLOWED_STATUSES else "unknown"


def clean_row(rec):
    """Return (sort_key, output_row) for a usable record, or None if it must be dropped."""
    order_id = rec.get("order_id", "").strip().upper()
    if not order_id:
        return None
    amount = parse_amount(rec.get("amount", ""))
    if amount is None:
        return None
    order_date = parse_date(rec.get("order_date", ""))
    if order_date is None:
        return None

    row = {
        "order_id": order_id,
        "customer_email": clean_email(rec.get("customer_email", "")),
        "amount": amount,
        "currency": clean_currency(rec.get("currency", ""), rec.get("amount", "")),
        "order_date": order_date,
        "status": clean_status(rec.get("status", "")),
    }
    updated_at = parse_updated_at(rec.get("updated_at", "")) or dt.datetime.min
    return updated_at, row


def read_records(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        lines = [line for line in f if line.strip() and not line.startswith("#")]
    reader = csv.reader(lines)
    try:
        header = next(reader)
    except StopIteration:
        return
    names = [re.sub(r"\s+", "_", name.strip().lower()) for name in header]
    for values in reader:
        yield dict(zip(names, values))


def main(argv):
    if len(argv) != 3:
        print("usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2

    # Keep the latest row per order_id; on a tie the later row wins (>= below).
    latest = {}
    for rec in read_records(argv[1]):
        cleaned = clean_row(rec)
        if cleaned is None:
            continue
        updated_at, row = cleaned
        current = latest.get(row["order_id"])
        if current is None or updated_at >= current[0]:
            latest[row["order_id"]] = (updated_at, row)

    rows = sorted(
        (row for _, row in latest.values()),
        key=lambda row: (row["order_date"], row["order_id"]),
    )
    with open(argv[2], "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(OUTPUT_FIELDS)
        for row in rows:
            writer.writerow([row[field] for field in OUTPUT_FIELDS])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
