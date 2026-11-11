#!/usr/bin/env python3
"""Normalize a messy order export into a stable, de-duplicated CSV."""

import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


OUTPUT_FIELDS = [
    "order_id",
    "customer_email",
    "amount",
    "currency",
    "order_date",
    "status",
]
REQUIRED_FIELDS = OUTPUT_FIELDS + ["updated_at"]
SYMBOL_CURRENCIES = {"$": "USD", "€": "EUR", "£": "GBP"}
ALLOWED_STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}


def parse_amount(raw):
    value = raw.strip()
    if not value:
        raise ValueError("empty amount")

    symbol_currency = next(
        (currency for symbol, currency in SYMBOL_CURRENCIES.items() if symbol in value),
        "",
    )
    value = value.replace("$", "").replace("€", "").replace("£", "")
    value = re.sub(r"\s+", "", value)
    negative = value.startswith("(") and value.endswith(")")
    if negative:
        value = value[1:-1]
    elif "(" in value or ")" in value:
        raise ValueError("invalid accounting amount")

    if "." in value and "," in value:
        decimal_separator = "." if value.rfind(".") > value.rfind(",") else ","
        thousands_separator = "," if decimal_separator == "." else "."
        value = value.replace(thousands_separator, "")
        if decimal_separator == ",":
            value = value.replace(",", ".")
    elif "," in value:
        if re.search(r",\d{2}$", value):
            value = value.replace(",", ".")
        else:
            value = value.replace(",", "")

    amount = Decimal(value)
    if negative:
        amount = -amount
    amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return format(amount, ".2f"), symbol_currency


def parse_order_date(raw):
    value = raw.strip()
    formats = (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d.%m.%Y",
        "%m/%d/%Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%b %d %Y",
        "%B %d %Y",
        "%d %b %Y",
        "%d %B %Y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError("invalid order date")


def updated_key(raw):
    value = raw.strip()
    if not value:
        return datetime.min
    if value.endswith("Z"):
        value = value[:-1]
    value = value.replace("T", " ")
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return datetime.min


def clean_row(values):
    order_id = values.get("order_id", "").strip().upper()
    if not order_id:
        return None
    try:
        amount, symbol_currency = parse_amount(values.get("amount", ""))
        order_date = parse_order_date(values.get("order_date", ""))
    except (ValueError, InvalidOperation):
        return None

    email = values.get("customer_email", "").strip().lower()
    if email.count("@") != 1 or not all(email.split("@")):
        email = ""

    currency = values.get("currency", "").strip().upper()
    currency = SYMBOL_CURRENCIES.get(currency, currency)
    if not currency:
        currency = symbol_currency or "USD"

    status = values.get("status", "").strip().lower()
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
        "_updated": updated_key(values.get("updated_at", "")),
    }


def normalize_header(header):
    return [re.sub(r"\s+", "_", name.strip().lower()) for name in header]


def clean_file(input_path, output_path):
    with open(input_path, "r", encoding="utf-8-sig", newline="") as source:
        filtered_lines = (line for line in source if line.strip() and not line.startswith("#"))
        reader = csv.reader(filtered_lines)
        try:
            header = normalize_header(next(reader))
        except StopIteration:
            header = []

        indices = {name: header.index(name) for name in REQUIRED_FIELDS if name in header}
        winners = {}
        for row_number, row in enumerate(reader):
            values = {
                field: row[index].strip() if index < len(row) else ""
                for field, index in indices.items()
            }
            cleaned = clean_row(values)
            if cleaned is None:
                continue
            cleaned["_row_number"] = row_number
            previous = winners.get(cleaned["order_id"])
            if previous is None or (cleaned["_updated"], row_number) >= (
                previous["_updated"],
                previous["_row_number"],
            ):
                winners[cleaned["order_id"]] = cleaned

    rows = sorted(winners.values(), key=lambda row: (row["order_date"], row["order_id"]))
    with open(output_path, "w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in OUTPUT_FIELDS})


def main(argv):
    if len(argv) != 3:
        print("Usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2
    clean_file(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
