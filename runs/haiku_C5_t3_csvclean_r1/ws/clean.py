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
SYMBOL_CURRENCIES = {"$": "USD", "€": "EUR", "£": "GBP"}

MONTHS = {}
for number, name in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"],
    start=1,
):
    MONTHS[name] = number
    MONTHS[name[:3]] = number

# Tried in order against the lowercased, trimmed date string.
DATE_PATTERNS = [
    re.compile(r"(?P<year>[0-9]{4})(?P<sep>[-/])(?P<month>[0-9]{1,2})(?P=sep)(?P<day>[0-9]{1,2})"),
    re.compile(r"(?P<day>[0-9]{1,2})\.(?P<month>[0-9]{1,2})\.(?P<year>[0-9]{4})"),  # day.month.year
    re.compile(r"(?P<month>[0-9]{1,2})/(?P<day>[0-9]{1,2})/(?P<year>[0-9]{4})"),  # month/day/year
    re.compile(r"(?P<monthname>[a-z]+)\.?\s+(?P<day>[0-9]{1,2}),?\s+(?P<year>[0-9]{4})"),
    re.compile(r"(?P<day>[0-9]{1,2})\s+(?P<monthname>[a-z]+)\.?,?\s+(?P<year>[0-9]{4})"),
]


def normalise_header(name):
    return name.strip().lower().replace(" ", "_")


def parse_amount(raw):
    """Return the amount as a Decimal rounded to 2 places, or None if unparseable."""
    s = raw.strip()
    negative = "(" in s or "-" in s
    body = re.sub(r"[\s$€£()+\-]", "", s)
    if not re.fullmatch(r"[0-9.,]*[0-9][0-9.,]*", body):
        return None

    if "." in body and "," in body:
        last = max(body.rfind("."), body.rfind(","))
        decimal = body[last]
        thousands = "," if decimal == "." else "."
        body = body.replace(thousands, "").replace(decimal, ".")
    elif "," in body:
        head, _, tail = body.rpartition(",")
        if len(tail) == 2:
            body = head.replace(",", "") + "." + tail
        else:
            body = body.replace(",", "")

    try:
        value = Decimal(body)
    except InvalidOperation:
        return None
    if negative:
        value = -value
    value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if value == 0:
        value = abs(value)
    return value


def parse_date(raw):
    """Return the date as YYYY-MM-DD, or None if missing or invalid."""
    s = raw.strip().lower()
    for pattern in DATE_PATTERNS:
        match = pattern.fullmatch(s)
        if match:
            break
    else:
        return None

    fields = match.groupdict()
    if "monthname" in fields:
        month = MONTHS.get(fields["monthname"])
    else:
        month = int(fields["month"])
    if month is None:
        return None
    try:
        return date(int(fields["year"]), month, int(fields["day"])).isoformat()
    except ValueError:
        return None


def parse_updated(raw):
    """Return a naive datetime, or None if empty or invalid (treated as oldest)."""
    s = raw.strip()
    if s.endswith("Z"):
        s = s[:-1]
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def normalise_email(raw):
    s = raw.strip().lower()
    if s.count("@") == 1:
        local, _, domain = s.partition("@")
        if local.strip() and domain.strip():
            return s
    return ""


def normalise_status(raw):
    s = raw.strip().lower()
    if s == "canceled":
        s = "cancelled"
    return s if s in ALLOWED_STATUSES else "unknown"


def read_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        lines = [line for line in f if line.strip() and not line.lstrip().startswith("#")]
    return list(csv.reader(lines))


def clean(src, dst):
    rows = read_rows(src)
    header = [normalise_header(name) for name in rows[0]] if rows else []
    columns = {}
    for i, name in enumerate(header):
        columns.setdefault(name, i)

    def field(row, name):
        i = columns.get(name)
        if i is None or i >= len(row):
            return ""
        return row[i]

    # order_id -> (sort key, output row); the key makes the latest update win,
    # with later file position breaking ties.
    best = {}
    for position, row in enumerate(rows[1:]):
        order_id = field(row, "order_id").strip().upper()
        if not order_id:
            continue
        amount_raw = field(row, "amount")
        amount = parse_amount(amount_raw)
        if amount is None:
            continue
        order_date = parse_date(field(row, "order_date"))
        if order_date is None:
            continue

        currency = field(row, "currency").strip()
        if currency:
            currency = SYMBOL_CURRENCIES.get(currency, currency.upper())
        else:
            currency = next(
                (SYMBOL_CURRENCIES[ch] for ch in amount_raw if ch in SYMBOL_CURRENCIES),
                "USD",
            )

        updated = parse_updated(field(row, "updated_at")) or datetime.min
        out_row = [
            order_id,
            normalise_email(field(row, "customer_email")),
            f"{amount:.2f}",
            currency,
            order_date,
            normalise_status(field(row, "status")),
        ]
        key = (updated, position)
        if order_id not in best or key > best[order_id][0]:
            best[order_id] = (key, out_row)

    out_rows = sorted((out for _, out in best.values()), key=lambda r: (r[4], r[0]))

    with open(dst, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(OUTPUT_HEADER)
        writer.writerows(out_rows)


def main():
    if len(sys.argv) != 3:
        print("usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2
    clean(sys.argv[1], sys.argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main())
