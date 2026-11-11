#!/usr/bin/env python3
"""Clean a messy order export: python3 clean.py INPUT.csv OUTPUT.csv"""

import csv
import datetime
import re
import sys
from decimal import ROUND_HALF_UP, Decimal

OUTPUT_COLUMNS = ["order_id", "customer_email", "amount", "currency", "order_date", "status"]
ALLOWED_STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
SYMBOL_CURRENCY = {"$": "USD", "€": "EUR", "£": "GBP"}
CENT = Decimal("0.01")

MONTHS = {}
for number, full in enumerate(
    ["january", "february", "march", "april", "may", "june",
     "july", "august", "september", "october", "november", "december"],
    start=1,
):
    MONTHS[full] = number
    MONTHS[full[:3]] = number

YMD = re.compile(r"(\d{4})([-/])(\d{1,2})\2(\d{1,2})")
DMY_DOT = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")
MDY_SLASH = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
MONTH_FIRST = re.compile(r"([a-z]+) (\d{1,2}), (\d{4})")
DAY_FIRST = re.compile(r"(\d{1,2}) ([a-z]+) (\d{4})")
UPDATED_AT = re.compile(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})Z?")


def parse_amount(raw):
    """Return (Decimal or None, currency symbol's currency or None)."""
    symbol = next((SYMBOL_CURRENCY[c] for c in raw if c in SYMBOL_CURRENCY), None)
    s = re.sub(r"[\s$€£]", "", raw)
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative, s = True, s[1:-1]
    elif s.startswith("-"):
        negative, s = True, s[1:]
    if not re.fullmatch(r"\d+(?:[.,]\d+)*", s):
        return None, symbol

    if "." in s and "," in s:
        decimal = "." if s.rfind(".") > s.rfind(",") else ","
        thousands = "," if decimal == "." else "."
        s = s.replace(thousands, "").replace(decimal, ".")
    elif "," in s and len(s) - s.rfind(",") - 1 == 2:
        head, tail = s.rsplit(",", 1)
        s = head.replace(",", "") + "." + tail
    else:
        s = s.replace(",", "")
    if not re.fullmatch(r"\d+(?:\.\d+)?", s):
        return None, symbol

    value = Decimal(s).quantize(CENT, rounding=ROUND_HALF_UP)
    if negative and value != 0:
        value = -value
    return value, symbol


def parse_date(raw):
    text = raw.strip().lower()
    if m := YMD.fullmatch(text):
        year, month, day = m[1], m[3], m[4]
    elif m := DMY_DOT.fullmatch(text):
        day, month, year = m[1], m[2], m[3]
    elif m := MDY_SLASH.fullmatch(text):
        month, day, year = m[1], m[2], m[3]
    elif m := MONTH_FIRST.fullmatch(text):
        month, day, year = MONTHS.get(m[1]), m[2], m[3]
    elif m := DAY_FIRST.fullmatch(text):
        day, month, year = m[1], MONTHS.get(m[2]), m[3]
    else:
        return None
    if month is None:
        return None
    try:
        return datetime.date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def clean_email(raw):
    text = raw.strip().lower()
    if text.count("@") == 1:
        local, _, domain = text.partition("@")
        if local and domain:
            return text
    return ""


def clean_currency(raw, symbol):
    text = raw.strip()
    if not text:
        return symbol or "USD"
    return SYMBOL_CURRENCY.get(text, text.upper())


def clean_status(raw):
    text = raw.strip().lower()
    if text == "canceled":
        text = "cancelled"
    return text if text in ALLOWED_STATUSES else "unknown"


def parse_updated(raw):
    m = UPDATED_AT.fullmatch(raw.strip())
    if not m:
        return datetime.datetime.min
    try:
        return datetime.datetime(*map(int, m.groups()))
    except ValueError:
        return datetime.datetime.min


def read_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        lines = [line for line in f if line.strip() and not line.startswith("#")]
    reader = csv.reader(lines)
    header = [h.strip().lower().replace(" ", "_") for h in next(reader, [])]
    for row in reader:
        yield dict(zip(header, row))


def clean_rows(rows):
    best = {}
    for index, row in enumerate(rows):
        def get(name):
            return row.get(name, "").strip()

        order_id = get("order_id").upper()
        if not order_id:
            continue
        amount, symbol = parse_amount(row.get("amount", ""))
        if amount is None:
            continue
        order_date = parse_date(row.get("order_date", ""))
        if order_date is None:
            continue

        record = {
            "order_id": order_id,
            "customer_email": clean_email(row.get("customer_email", "")),
            "amount": format(amount, ".2f"),
            "currency": clean_currency(row.get("currency", ""), symbol),
            "order_date": order_date,
            "status": clean_status(row.get("status", "")),
        }
        key = (parse_updated(row.get("updated_at", "")), index)
        if order_id not in best or key > best[order_id][0]:
            best[order_id] = (key, record)

    records = [record for _, record in best.values()]
    return sorted(records, key=lambda r: (r["order_date"], r["order_id"]))


def write_rows(path, records):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(OUTPUT_COLUMNS)
        for record in records:
            writer.writerow([record[c] for c in OUTPUT_COLUMNS])


def main(argv):
    if len(argv) != 3:
        print("usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2
    write_rows(argv[2], clean_rows(read_rows(argv[1])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
