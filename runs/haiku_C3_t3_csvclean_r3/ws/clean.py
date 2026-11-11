#!/usr/bin/env python3
"""Clean a messy shop order export: python3 clean.py INPUT.csv OUTPUT.csv"""
import csv
import datetime
import re
import sys
from decimal import Decimal, ROUND_HALF_UP

OUTPUT_FIELDS = ["order_id", "customer_email", "amount", "currency", "order_date", "status"]
SYMBOL_CURRENCY = {"$": "USD", "€": "EUR", "£": "GBP"}
ALLOWED_STATUS = {"pending", "paid", "shipped", "cancelled", "refunded"}
CENT = Decimal("0.01")

MONTHS = {}
for number, name in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"],
    start=1,
):
    MONTHS[name] = number
    MONTHS[name[:3]] = number


def parse_amount(raw):
    """Return the amount as a Decimal rounded to cents, or None if unusable."""
    s = re.sub(r"[\s$€£]", "", raw)
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative, s = True, s[1:-1]
    elif s.startswith("-"):
        negative, s = True, s[1:]

    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        if re.fullmatch(r"\d\d", tail):
            s = head.replace(",", "") + "." + tail
        else:
            s = s.replace(",", "")

    if not re.fullmatch(r"\d*\.?\d+", s):
        return None
    value = Decimal(s).quantize(CENT, rounding=ROUND_HALF_UP)
    if negative and value:
        value = -value
    return value


def _make_date(year, month, day):
    if month is None:
        return None
    try:
        return datetime.date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def parse_date(raw):
    """Return the date as YYYY-MM-DD, or None if missing or invalid."""
    s = raw.strip()
    m = re.fullmatch(r"(\d{4})([-/])(\d{1,2})\2(\d{1,2})", s)
    if m:
        return _make_date(m[1], m[3], m[4])
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)  # day.month.year
    if m:
        return _make_date(m[3], m[2], m[1])
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)  # month/day/year
    if m:
        return _make_date(m[3], m[1], m[2])
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", s)  # Mar 4, 2026
    if m:
        return _make_date(m[3], MONTHS.get(m[1].lower()), m[2])
    m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)  # 4 Mar 2026
    if m:
        return _make_date(m[3], MONTHS.get(m[2].lower()), m[1])
    return None


def parse_updated(raw):
    """Return a sortable datetime; empty or invalid values sort as oldest."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})Z?", raw.strip())
    if not m:
        return datetime.datetime.min
    try:
        return datetime.datetime(*map(int, m.groups()))
    except ValueError:
        return datetime.datetime.min


def normalise_email(raw):
    s = raw.strip().lower()
    local, sep, domain = s.partition("@")
    if sep and local and domain and "@" not in domain:
        return s
    return ""


def normalise_status(raw):
    s = raw.strip().lower()
    if s == "canceled":
        s = "cancelled"
    return s if s in ALLOWED_STATUS else "unknown"


def resolve_currency(field_value, amount_raw):
    code = field_value.strip().upper()
    if not code:
        code = next((SYMBOL_CURRENCY[c] for c in amount_raw if c in SYMBOL_CURRENCY), "USD")
    return SYMBOL_CURRENCY.get(code, code)


def read_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        lines = [line for line in f if line.strip() and not line.startswith("#")]
    return list(csv.reader(lines))


def clean(rows):
    if not rows:
        return []
    header = [h.strip().lower().replace(" ", "_") for h in rows[0]]
    index = {name: i for i, name in enumerate(header)}

    def field(row, name):
        i = index.get(name)
        return row[i].strip() if i is not None and i < len(row) else ""

    kept = {}  # order_id -> (de-duplication key, record)
    for n, row in enumerate(rows[1:]):
        order_id = field(row, "order_id").upper()
        if not order_id:
            continue
        amount = parse_amount(field(row, "amount"))
        if amount is None:
            continue
        order_date = parse_date(field(row, "order_date"))
        if order_date is None:
            continue
        record = {
            "order_id": order_id,
            "customer_email": normalise_email(field(row, "customer_email")),
            "amount": f"{amount:.2f}",
            "currency": resolve_currency(field(row, "currency"), field(row, "amount")),
            "order_date": order_date,
            "status": normalise_status(field(row, "status")),
        }
        key = (parse_updated(field(row, "updated_at")), n)
        if order_id not in kept or key > kept[order_id][0]:
            kept[order_id] = (key, record)

    records = [record for _, record in kept.values()]
    return sorted(records, key=lambda r: (r["order_date"], r["order_id"]))


def main(argv):
    if len(argv) != 3:
        sys.exit(f"usage: {argv[0]} INPUT.csv OUTPUT.csv")
    records = clean(read_rows(argv[1]))
    with open(argv[2], "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


if __name__ == "__main__":
    main(sys.argv)
