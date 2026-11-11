#!/usr/bin/env python3
"""Clean a messy order export.

Usage: python3 clean.py INPUT.csv OUTPUT.csv
"""

import csv
import datetime as dt
import re
import sys
from decimal import ROUND_HALF_UP, Decimal

OUTPUT_HEADER = ["order_id", "customer_email", "amount", "currency", "order_date", "status"]
ALLOWED_STATUS = {"pending", "paid", "shipped", "cancelled", "refunded"}
SYMBOL_CURRENCY = {"$": "USD", "€": "EUR", "£": "GBP"}
OLDEST = dt.datetime.min

MONTHS = {}
for _num, (_short, _full) in enumerate(
    [
        ("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"),
        ("may", "may"), ("jun", "june"), ("jul", "july"), ("aug", "august"),
        ("sep", "september"), ("oct", "october"), ("nov", "november"), ("dec", "december"),
    ],
    start=1,
):
    MONTHS[_short] = _num
    MONTHS[_full] = _num

# Each accepted textual form, with the meaning of its capture groups in order.
# y/m/d are numeric fields, M is an English month name.
DATE_FORMATS = [
    (r"(\d{4})-(\d{1,2})-(\d{1,2})", ("y", "m", "d")),
    (r"(\d{4})/(\d{1,2})/(\d{1,2})", ("y", "m", "d")),
    (r"(\d{1,2})\.(\d{1,2})\.(\d{4})", ("d", "m", "y")),
    (r"(\d{1,2})/(\d{1,2})/(\d{4})", ("m", "d", "y")),
    (r"([A-Za-z]+) (\d{1,2}), (\d{4})", ("M", "d", "y")),
    (r"(\d{1,2}) ([A-Za-z]+) (\d{4})", ("d", "M", "y")),
]

UPDATED_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})Z?")


def normalise_header(name):
    return name.strip().lower().replace(" ", "_")


def value(row, col, name):
    i = col.get(name)
    if i is None or i >= len(row):
        return ""
    return row[i]


def parse_amount(raw):
    """Return (Decimal rounded to 2 places, currency symbol or None), or None if unparseable."""
    symbol = next((ch for ch in raw if ch in SYMBOL_CURRENCY), None)
    s = re.sub(r"[$€£\s]", "", raw)

    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    elif s.startswith("-"):
        negative = True
        s = s[1:]
    if any(ch in s for ch in "()-"):
        return None

    # The last of '.' and ',' is the decimal separator when both appear.
    # A lone ',' is decimal only when exactly two digits follow it.
    # A lone '.' is always decimal.
    if "." in s and "," in s:
        dec = "," if s.rindex(",") > s.rindex(".") else "."
    elif "," in s:
        dec = "," if re.search(r",\d{2}$", s) else None
    elif "." in s:
        dec = "."
    else:
        dec = None

    if dec is None:
        int_part, frac = s, ""
    else:
        int_part, _, frac = s.rpartition(dec)
        if dec == "." and "." in int_part:
            return None  # more than one decimal point
    int_part = re.sub(r"[.,]", "", int_part)
    normalised = int_part + ("." + frac if dec else "")
    if not re.fullmatch(r"\d*(\.\d*)?", normalised) or not re.search(r"\d", normalised):
        return None

    result = Decimal(normalised)
    if negative:
        result = -result
    result = result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return abs(result) if result.is_zero() else result, symbol


def parse_date(raw):
    s = raw.strip()
    for pattern, layout in DATE_FORMATS:
        m = re.fullmatch(pattern, s)
        if not m:
            continue
        parts = dict(zip(layout, m.groups()))
        if "M" in parts:
            month = MONTHS.get(parts["M"].lower())
        else:
            month = int(parts["m"])
        if month is None:
            return None
        try:
            return dt.date(int(parts["y"]), month, int(parts["d"]))
        except ValueError:
            return None
    return None


def parse_updated(raw):
    m = UPDATED_RE.fullmatch(raw.strip())
    if not m:
        return OLDEST  # empty or unrecognised: treated as oldest
    try:
        return dt.datetime(*(int(g) for g in m.groups()))
    except ValueError:
        return OLDEST


def clean_email(raw):
    s = raw.strip().lower()
    local, sep, domain = s.partition("@")
    if sep and local.strip() and domain.strip() and "@" not in domain:
        return s
    return ""


def clean_currency(raw, symbol):
    s = raw.strip()
    if not s:
        return SYMBOL_CURRENCY[symbol] if symbol else "USD"
    return SYMBOL_CURRENCY.get(s, s).upper()


def clean_status(raw):
    s = raw.strip().lower()
    if s == "canceled":
        s = "cancelled"
    return s if s in ALLOWED_STATUS else "unknown"


def read_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        lines = [line for line in f if line.strip() and not line.startswith("#")]
    return list(csv.reader(lines))


def clean_rows(rows):
    if not rows:
        return []
    col = {}
    for i, name in enumerate(normalise_header(h) for h in rows[0]):
        col.setdefault(name, i)

    best = {}  # order_id -> (updated_at, record); later rows win ties
    for row in rows[1:]:
        order_id = value(row, col, "order_id").strip().upper()
        if not order_id:
            continue
        amount = parse_amount(value(row, col, "amount"))
        if amount is None:
            continue
        order_date = parse_date(value(row, col, "order_date"))
        if order_date is None:
            continue

        amount_value, symbol = amount
        updated = parse_updated(value(row, col, "updated_at"))
        record = {
            "order_id": order_id,
            "customer_email": clean_email(value(row, col, "customer_email")),
            "amount": f"{amount_value:.2f}",
            "currency": clean_currency(value(row, col, "currency"), symbol),
            "order_date": order_date,
            "status": clean_status(value(row, col, "status")),
        }
        if order_id not in best or updated >= best[order_id][0]:
            best[order_id] = (updated, record)

    records = [rec for _, rec in best.values()]
    records.sort(key=lambda r: (r["order_date"], r["order_id"]))
    return records


def main(argv):
    if len(argv) != 3:
        print("usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2
    records = clean_rows(read_rows(argv[1]))
    with open(argv[2], "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(OUTPUT_HEADER)
        for r in records:
            writer.writerow([
                r["order_id"],
                r["customer_email"],
                r["amount"],
                r["currency"],
                r["order_date"].isoformat(),
                r["status"],
            ])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
