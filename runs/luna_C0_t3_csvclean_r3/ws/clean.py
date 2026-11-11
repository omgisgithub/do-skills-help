#!/usr/bin/env python3
"""Normalize a messy order export into the canonical CSV format."""

import csv
import datetime as dt
import re
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


OUTPUT_FIELDS = [
    "order_id", "customer_email", "amount", "currency", "order_date", "status"
]
REQUIRED_FIELDS = OUTPUT_FIELDS + ["updated_at"]
SYMBOL_CURRENCIES = {"$": "USD", "€": "EUR", "£": "GBP"}
ALLOWED_STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}


def parse_amount(value):
    """Return (formatted amount, currency symbol found) or (None, symbol)."""
    value = value.strip()
    symbol = next((s for s in SYMBOL_CURRENCIES if s in value), "")
    value = value.replace("$", "").replace("€", "").replace("£", "")
    value = re.sub(r"\s+", "", value)
    if not value:
        return None, symbol

    negative = value.startswith("(") and value.endswith(")")
    if negative:
        value = value[1:-1]
    elif "(" in value or ")" in value:
        return None, symbol

    if "." in value and "," in value:
        decimal_sep = "." if value.rfind(".") > value.rfind(",") else ","
        thousands_sep = "," if decimal_sep == "." else "."
        value = value.replace(thousands_sep, "").replace(decimal_sep, ".")
    elif "," in value:
        tail = value.rsplit(",", 1)[1]
        if len(tail) == 2:
            value = value.replace(",", ".")
        else:
            value = value.replace(",", "")
    # A lone dot is the decimal separator. Reject malformed punctuation and
    # non-numeric characters instead of silently stripping them.
    if not re.fullmatch(r"\d+(?:\.\d+)?", value):
        return None, symbol
    try:
        amount = Decimal(value)
        if negative:
            amount = -amount
        amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None, symbol
    return format(amount, ".2f"), symbol


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
    return None


def parse_updated(value):
    """Parse the supported timestamp; invalid or empty timestamps are oldest."""
    value = value.strip()
    if not value:
        return dt.datetime.min
    if value.endswith("Z"):
        value = value[:-1]
    try:
        return dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        try:
            return dt.datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return dt.datetime.min


def normalize_header(value):
    return value.strip().lower().replace(" ", "_")


def clean(input_path, output_path):
    latest = {}
    with open(input_path, "r", encoding="utf-8-sig", newline="") as source:
        # Filter physical blank/comment lines before handing content to csv;
        # comments are defined by their first character, with no leading trim.
        lines = (line for line in source if line.strip() and not line.startswith("#"))
        reader = csv.DictReader(lines)
        if reader.fieldnames is None:
            rows = []
        else:
            mapping = {}
            for original in reader.fieldnames:
                key = normalize_header(original)
                if key in REQUIRED_FIELDS and key not in mapping:
                    mapping[key] = original
            if not set(REQUIRED_FIELDS).issubset(mapping):
                raise ValueError("input is missing one or more required columns")

            rows = []
            for position, raw in enumerate(reader):
                def get(field):
                    value = raw.get(mapping[field], "")
                    return value.strip() if isinstance(value, str) else ""

                order_id = get("order_id").upper()
                if not order_id:
                    continue
                amount, symbol = parse_amount(get("amount"))
                date = parse_date(get("order_date"))
                if amount is None or date is None:
                    continue

                email = get("customer_email").lower()
                if email.count("@") != 1 or not all(email.split("@")):
                    email = ""
                currency = get("currency").upper()
                currency = SYMBOL_CURRENCIES.get(currency, currency)
                if not currency:
                    currency = SYMBOL_CURRENCIES.get(symbol, "USD")
                status = get("status").lower()
                if status == "canceled":
                    status = "cancelled"
                if status not in ALLOWED_STATUSES:
                    status = "unknown"

                updated = parse_updated(get("updated_at"))
                record = {
                    "order_id": order_id,
                    "customer_email": email,
                    "amount": amount,
                    "currency": currency,
                    "order_date": date,
                    "status": status,
                }
                prior = latest.get(order_id)
                if prior is None or (updated, position) >= (prior[0], prior[1]):
                    latest[order_id] = (updated, position, record)

    ordered = sorted(
        (item[2] for item in latest.values()),
        key=lambda row: (row["order_date"], row["order_id"]),
    )
    with open(output_path, "w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ordered)


def main(argv):
    if len(argv) != 3:
        print("Usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2
    try:
        clean(argv[1], argv[2])
    except (OSError, csv.Error, ValueError) as exc:
        print("clean.py: {}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
