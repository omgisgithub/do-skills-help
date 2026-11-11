#!/usr/bin/env python3
"""Normalize a shop order CSV export."""

import csv
import datetime as dt
import re
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


FIELDS = ("order_id", "customer_email", "amount", "currency", "order_date", "status", "updated_at")
CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
ALLOWED_STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}


def normalize_header(value):
    return value.strip().lower().replace(" ", "_")


def parse_amount(value):
    raw = value.strip()
    symbol = next((CURRENCY_SYMBOLS[ch] for ch in raw if ch in CURRENCY_SYMBOLS), "")
    negative = raw.startswith("(") and raw.endswith(")")
    if negative:
        raw = raw[1:-1]
    raw = "".join(ch for ch in raw if ch not in CURRENCY_SYMBOLS and not ch.isspace())
    if not raw:
        raise ValueError("empty amount")

    comma, dot = raw.rfind(","), raw.rfind(".")
    if comma >= 0 and dot >= 0:
        decimal_sep = "," if comma > dot else "."
        thousands_sep = "." if decimal_sep == "," else ","
    elif comma >= 0:
        decimal_sep = "," if len(raw) - comma - 1 == 2 else None
        thousands_sep = "." if decimal_sep else ","
    else:
        decimal_sep = "." if dot >= 0 else None
        thousands_sep = ","

    if decimal_sep:
        raw = raw.replace(thousands_sep, "").replace(decimal_sep, ".")
    else:
        raw = raw.replace(",", "").replace(".", "") if comma >= 0 else raw
    try:
        number = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError("invalid amount") from exc
    if not number.is_finite():
        raise ValueError("invalid amount")
    if negative:
        number = -number
    return format(number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f"), symbol


def parse_date(value):
    value = value.strip()
    formats = (
        "%Y-%m-%d", "%Y/%m/%d", "%d.%m.%Y", "%m/%d/%Y",
        "%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y",
        "%d %b %Y", "%d %B %Y",
    )
    for fmt in formats:
        try:
            return dt.datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError("invalid date")


def updated_key(value):
    value = value.strip()
    if not value:
        return (0, dt.datetime.min)
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(Z)?", value)
    if not match:
        return (0, dt.datetime.min)
    try:
        return (1, dt.datetime.strptime(match.group(1) + "T" + match.group(2), "%Y-%m-%dT%H:%M:%S"))
    except ValueError:
        return (0, dt.datetime.min)


def clean_row(row, indexes):
    def value(field):
        index = indexes.get(field)
        return row[index].strip() if index is not None and index < len(row) else ""

    order_id = value("order_id").upper()
    if not order_id:
        return None
    email = value("customer_email").lower()
    if email.count("@") != 1 or any(not part for part in email.split("@")):
        email = ""
    try:
        amount, amount_currency = parse_amount(value("amount"))
        order_date = parse_date(value("order_date"))
    except ValueError:
        return None
    currency = value("currency").upper()
    currency = CURRENCY_SYMBOLS.get(currency, currency)
    if not currency:
        currency = amount_currency or "USD"
    status = value("status").lower()
    if status == "canceled":
        status = "cancelled"
    if status not in ALLOWED_STATUSES:
        status = "unknown"
    return order_id, email, amount, currency, order_date, status


def main(argv):
    if len(argv) != 3:
        print("Usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2
    input_path, output_path = argv[1:]
    with open(input_path, "r", encoding="utf-8-sig", newline="") as source:
        lines = (line for line in source if line.strip() and not line.startswith("#"))
        reader = csv.reader(lines)
        try:
            header = next(reader)
        except StopIteration:
            header = []
        normalized = [normalize_header(name) for name in header]
        indexes = {field: normalized.index(field) for field in FIELDS if field in normalized}
        latest = {}
        for position, row in enumerate(reader):
            result = clean_row(row, indexes)
            if result is None:
                continue
            key = (updated_key(row[indexes["updated_at"]])
                   if "updated_at" in indexes and indexes["updated_at"] < len(row) else (0, dt.datetime.min))
            order_id = result[0]
            if order_id not in latest or key >= latest[order_id][0]:
                latest[order_id] = (key, position, result)

    rows = [entry[2] for entry in latest.values()]
    rows.sort(key=lambda item: (item[4], item[0]))
    with open(output_path, "w", encoding="utf-8", newline="") as destination:
        writer = csv.writer(destination, lineterminator="\n")
        writer.writerow(("order_id", "customer_email", "amount", "currency", "order_date", "status"))
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
