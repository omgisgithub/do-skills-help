#!/usr/bin/env python3
"""Normalize an order export: python3 clean.py INPUT.csv OUTPUT.csv."""

import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext


FIELDS = ("order_id", "customer_email", "amount", "currency", "order_date", "status")
SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
MONTHS = {}
for number, month in enumerate(
    ("january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"), 1
):
    MONTHS[month] = MONTHS[month[:3]] = number


def parse_amount(value):
    text = "".join(char for char in value if not char.isspace() and char not in SYMBOLS)
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    if "." in text and "," in text:
        if text.rfind(".") > text.rfind(","):
            text = text.replace(",", "")
        else:
            text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        whole, fraction = text.rsplit(",", 1)
        if re.fullmatch(r"[0-9]{2}", fraction):
            text = whole.replace(",", "") + "." + fraction
        else:
            text = text.replace(",", "")
    if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", text):
        raise ValueError("invalid amount")
    if negative and text.startswith(("+", "-")):
        raise ValueError("signed accounting amount")
    with localcontext() as context:
        context.prec = max(28, len(text) + 4)
        amount = Decimal(text)
        if negative:
            amount = -amount
        return format(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")


def parse_date(value):
    match = re.fullmatch(r"([0-9]{4})([-/])([0-9]{1,2})\2([0-9]{1,2})", value)
    if match:
        year, _, month, day = match.groups()
    else:
        match = re.fullmatch(r"([0-9]{1,2})\.([0-9]{1,2})\.([0-9]{4})", value)
        if match:
            day, month, year = match.groups()
        else:
            match = re.fullmatch(r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})", value)
            if match:
                month, day, year = match.groups()
            else:
                match = re.fullmatch(r"([a-z]+)\s+([0-9]{1,2}),\s+([0-9]{4})", value.lower())
                if match:
                    month, day, year = match.groups()
                else:
                    match = re.fullmatch(r"([0-9]{1,2})\s+([a-z]+)\s+([0-9]{4})", value.lower())
                    if not match:
                        raise ValueError("invalid date format")
                    day, month, year = match.groups()
                if month not in MONTHS:
                    raise ValueError("invalid month")
                month = MONTHS[month]
    return date(int(year), int(month), int(day)).isoformat()


def parse_updated_at(value):
    # Malformed timestamps, like missing timestamps, have no usable update time.
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}Z?", value):
        return datetime.min
    try:
        return datetime.fromisoformat(value.rstrip("Z"))
    except ValueError:
        return datetime.min


def clean(input_path, output_path):
    orders = {}
    with open(input_path, encoding="utf-8-sig", newline="") as source:
        lines = (line for line in source if line.strip() and not line.startswith("#"))
        reader = csv.DictReader(lines)
        if reader.fieldnames is not None:
            reader.fieldnames = [name.strip().lower().replace(" ", "_") for name in reader.fieldnames]
        for raw in reader:
            row = {key: (raw.get(key) or "").strip() for key in FIELDS + ("updated_at",)}
            order_id = row["order_id"].upper()
            if not order_id:
                continue
            try:
                amount = parse_amount(row["amount"])
                order_date = parse_date(row["order_date"])
            except (ValueError, InvalidOperation):
                continue
            email = row["customer_email"].lower()
            if email.count("@") != 1 or not all(email.split("@")):
                email = ""
            currency = row["currency"].upper()
            if not currency:
                currency = next((SYMBOLS[char] for char in row["amount"] if char in SYMBOLS), "USD")
            currency = SYMBOLS.get(currency, currency)
            status = row["status"].lower()
            if status == "canceled":
                status = "cancelled"
            if status not in STATUSES:
                status = "unknown"
            updated = parse_updated_at(row["updated_at"])
            result = (order_id, email, amount, currency, order_date, status)
            if order_id not in orders or updated >= orders[order_id][0]:
                orders[order_id] = (updated, result)
    with open(output_path, "w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target, lineterminator="\n")
        writer.writerow(FIELDS)
        writer.writerows(sorted((item[1] for item in orders.values()), key=lambda row: (row[4], row[0])))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: python3 clean.py INPUT.csv OUTPUT.csv")
    clean(sys.argv[1], sys.argv[2])
