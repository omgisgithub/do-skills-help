#!/usr/bin/env python3
"""Normalize the shop's order CSV exports."""

import csv
import datetime as dt
import decimal
import re
import sys


OUTPUT_FIELDS = [
    "order_id", "customer_email", "amount", "currency", "order_date", "status"
]
REQUIRED_FIELDS = OUTPUT_FIELDS + ["updated_at"]
SYMBOL_CURRENCIES = {"$": "USD", "€": "EUR", "£": "GBP"}
ALLOWED_STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}


def normalize_header(value):
    return (value or "").strip().lower().replace(" ", "_")


def parse_amount(value):
    text = (value or "").strip()
    if not text:
        raise ValueError("empty amount")
    symbol = next((s for s in SYMBOL_CURRENCIES if s in text), None)
    text = text.replace("$", "").replace("€", "").replace("£", "")
    text = re.sub(r"\s+", "", text)
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    elif "(" in text or ")" in text:
        raise ValueError("bad parentheses")

    if "." in text and "," in text:
        decimal_sep = "." if text.rfind(".") > text.rfind(",") else ","
        thousands_sep = "," if decimal_sep == "." else "."
        text = text.replace(thousands_sep, "")
        if decimal_sep == ",":
            text = text.replace(",", ".")
    elif "," in text:
        tail = text.rsplit(",", 1)[1]
        if len(tail) == 2 and tail.isdigit():
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")
    # A lone dot is the decimal separator.
    amount = decimal.Decimal(text)
    if negative:
        amount = -amount
    amount = amount.quantize(decimal.Decimal("0.01"), rounding=decimal.ROUND_HALF_UP)
    return format(amount, ".2f"), symbol


def parse_date(value):
    value = (value or "").strip()
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
    value = (value or "").strip()
    if not value:
        return dt.datetime.min
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})Z?", value)
    if not match:
        return dt.datetime.min
    try:
        return dt.datetime.strptime("T".join(match.groups()), "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return dt.datetime.min


def clean_row(row):
    values = {key: (row.get(key) or "").strip() for key in REQUIRED_FIELDS}
    order_id = values["order_id"].upper()
    if not order_id:
        return None
    try:
        amount, symbol = parse_amount(values["amount"])
        order_date = parse_date(values["order_date"])
    except (ValueError, decimal.InvalidOperation):
        return None

    email = values["customer_email"].lower()
    if email.count("@") != 1 or not all(email.split("@")):
        email = ""
    currency = values["currency"].upper()
    if currency in SYMBOL_CURRENCIES:
        currency = SYMBOL_CURRENCIES[currency]
    elif not currency:
        currency = SYMBOL_CURRENCIES.get(symbol, "USD")
    status = values["status"].lower()
    if status == "canceled":
        status = "cancelled"
    if status not in ALLOWED_STATUSES:
        status = "unknown"
    return {
        "order_id": order_id,
        "customer_email": email,
        "amount": amount,
        "currency": currency,
        "order_date": order_date,
        "status": status,
        "_updated": updated_key(values["updated_at"]),
    }


def main(argv):
    if len(argv) != 3:
        print("Usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2
    input_path, output_path = argv[1:]
    with open(input_path, "r", encoding="utf-8-sig", newline="") as source:
        # Filter whole comment and blank lines before handing records to csv.
        lines = (line for line in source if line.strip() and not line.startswith("#"))
        reader = csv.DictReader(lines)
        if reader.fieldnames is None:
            records = []
        else:
            reader.fieldnames = [normalize_header(name) for name in reader.fieldnames]
            winners = {}
            for position, raw in enumerate(reader):
                row = clean_row(raw)
                if row is None:
                    continue
                row["_position"] = position
                previous = winners.get(row["order_id"])
                if previous is None or (row["_updated"], position) >= (previous["_updated"], previous["_position"]):
                    winners[row["order_id"]] = row
            records = sorted(winners.values(), key=lambda row: (row["order_date"], row["order_id"]))

    with open(output_path, "w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in records:
            writer.writerow({key: row[key] for key in OUTPUT_FIELDS})
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
