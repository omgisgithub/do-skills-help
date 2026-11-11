#!/usr/bin/env python3
"""Clean a messy shop order export.

Usage: python3 clean.py INPUT.csv OUTPUT.csv
"""

import csv
import re
import sys
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

OUTPUT_COLUMNS = ["order_id", "customer_email", "amount", "currency", "order_date", "status"]
CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}

MONTHS = {}
for _number, _name in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"],
    start=1,
):
    MONTHS[_name] = _number
    MONTHS[_name[:3]] = _number

# Named groups: y, m, d (numeric month) or mon (English month name).
DATE_PATTERNS = [
    re.compile(r"(?P<y>\d{4})[-/](?P<m>\d{1,2})[-/](?P<d>\d{1,2})"),  # 2026-03-04, 2026/03/04
    re.compile(r"(?P<d>\d{1,2})\.(?P<m>\d{1,2})\.(?P<y>\d{4})"),      # 04.03.2026 (day.month.year)
    re.compile(r"(?P<m>\d{1,2})/(?P<d>\d{1,2})/(?P<y>\d{4})"),        # 03/04/2026 (month/day/year)
    re.compile(r"(?P<mon>[a-z]+)\.?\s+(?P<d>\d{1,2}),?\s+(?P<y>\d{4})", re.IGNORECASE),  # Mar 4, 2026
    re.compile(r"(?P<d>\d{1,2})\s+(?P<mon>[a-z]+)\.?,?\s+(?P<y>\d{4})", re.IGNORECASE),  # 4 Mar 2026
]

UPDATED_RE = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})[T ](?P<time>\d{2}:\d{2}:\d{2})Z?")


def read_rows(path):
    # Drop blank lines and comment lines before CSV parsing; utf-8-sig strips a BOM.
    with open(path, encoding="utf-8-sig", newline="") as f:
        lines = [line for line in f.readlines() if line.strip() and not line.startswith("#")]
    return csv.reader(lines)


def field(raw, col, name):
    i = col.get(name)
    if i is None or i >= len(raw):
        return ""
    return raw[i].strip()


def parse_amount(raw):
    """Return (Decimal rounded to 2 places, currency symbol or None), or None if unparseable."""
    symbol = next((c for c in raw if c in CURRENCY_SYMBOLS), None)
    s = re.sub(r"[\s$€£]", "", raw)

    negative = s.startswith("(") and s.endswith(")")
    if negative:
        s = s[1:-1]
    if not re.fullmatch(r"-?[0-9.,]+", s):
        return None
    if negative:
        if s.startswith("-"):
            return None
        s = "-" + s

    if "." in s and "," in s:
        # Whichever separator comes last is the decimal; the other is thousands.
        if s.rfind(".") > s.rfind(","):
            s = s.replace(",", "")
        else:
            s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        if len(tail) == 2 and tail.isdigit():
            s = head.replace(",", "") + "." + tail
        else:
            s = s.replace(",", "")

    try:
        value = Decimal(s).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None
    if value.is_zero():
        value = Decimal("0.00")  # avoid "-0.00"
    return value, symbol


def parse_date(raw):
    s = raw.strip()
    for pattern in DATE_PATTERNS:
        match = pattern.fullmatch(s)
        if match:
            break
    else:
        return None

    parts = match.groupdict()
    if "mon" in parts:
        month = MONTHS.get(parts["mon"].lower())
    else:
        month = int(parts["m"])
    if month is None:
        return None
    try:
        return date(int(parts["y"]), month, int(parts["d"])).isoformat()
    except ValueError:
        return None


def parse_updated(raw):
    # Empty or invalid values sort as the oldest possible.
    match = UPDATED_RE.fullmatch(raw.strip())
    if match:
        try:
            return datetime.strptime(f"{match['date']} {match['time']}", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return datetime.min


def clean_email(raw):
    s = raw.lower()
    local, _, domain = s.partition("@")
    if s.count("@") == 1 and local.strip() and domain.strip():
        return s
    return ""


def clean_status(raw):
    s = raw.lower()
    if s == "canceled":
        s = "cancelled"
    return s if s in STATUSES else "unknown"


def main():
    if len(sys.argv) != 3:
        print("usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2

    reader = read_rows(sys.argv[1])
    header = next(reader, [])
    col = {}
    for i, name in enumerate(header):
        col.setdefault(name.strip().lower().replace(" ", "_"), i)

    # order_id -> ((updated_at, file position), output row); later entries win ties.
    kept = {}
    for index, raw in enumerate(reader):
        if not raw:
            continue

        order_id = field(raw, col, "order_id").upper()
        amount = parse_amount(field(raw, col, "amount"))
        order_date = parse_date(field(raw, col, "order_date"))
        if not order_id or amount is None or order_date is None:
            continue
        value, symbol = amount

        currency = field(raw, col, "currency").upper()
        currency = CURRENCY_SYMBOLS.get(currency, currency)
        if not currency:
            currency = CURRENCY_SYMBOLS.get(symbol, "USD")

        out = {
            "order_id": order_id,
            "customer_email": clean_email(field(raw, col, "customer_email").lower()),
            "amount": str(value),
            "currency": currency,
            "order_date": order_date,
            "status": clean_status(field(raw, col, "status")),
        }

        key = (parse_updated(field(raw, col, "updated_at")), index)
        if order_id not in kept or key > kept[order_id][0]:
            kept[order_id] = (key, out)

    rows = sorted((out for _, out in kept.values()), key=lambda r: (r["order_date"], r["order_id"]))

    with open(sys.argv[2], "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(OUTPUT_COLUMNS)
        for r in rows:
            writer.writerow([r[c] for c in OUTPUT_COLUMNS])
    return 0


if __name__ == "__main__":
    sys.exit(main())
