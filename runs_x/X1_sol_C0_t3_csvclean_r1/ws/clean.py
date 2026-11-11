#!/usr/bin/env python3
"""Normalize shop exports: python3 clean.py INPUT.csv OUTPUT.csv."""

import argparse
import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from itertools import chain
import re


FIELDS = ("order_id", "customer_email", "amount", "currency", "order_date", "status")
SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
MONTHS = {}
for number, name in enumerate(
    ("january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"), 1
):
    MONTHS[name] = MONTHS[name[:3]] = number


def records(stream):
    """Skip export comments and blank lines outside quoted CSV records."""
    lines = iter(stream)
    for line in lines:
        if not line.strip() or line.startswith("#"):
            continue
        # A quoted field can consume more lines from the shared iterator.
        yield next(csv.reader(chain((line,), lines)))


def parse_amount(value):
    value = "".join(c for c in value if not c.isspace() and c not in SYMBOLS)
    negative = value.startswith("(") and value.endswith(")")
    if negative:
        value = value[1:-1]
        if value.startswith(("+", "-")):
            raise ValueError("signed accounting amount")
    if "." in value and "," in value:
        decimal, thousands = (".", ",") if value.rfind(".") > value.rfind(",") else (",", ".")
        value = value.replace(thousands, "").replace(decimal, ".")
    elif "," in value:
        whole, fraction = value.rsplit(",", 1)
        if re.fullmatch(r"[0-9]{2}", fraction):
            value = whole.replace(",", "") + "." + fraction
        else:
            value = value.replace(",", "")
    if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", value):
        raise ValueError("invalid amount")
    with localcontext() as context:
        context.prec = max(28, len(value) + 4)
        amount = Decimal(value)
        if negative:
            amount = -amount
        return format(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")


def parse_date(value):
    for pattern, order in (
        (r"([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})", "ymd"),
        (r"([0-9]{4})/([0-9]{1,2})/([0-9]{1,2})", "ymd"),
        (r"([0-9]{1,2})\.([0-9]{1,2})\.([0-9]{4})", "dmy"),
        (r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})", "mdy"),
    ):
        match = re.fullmatch(pattern, value)
        if match:
            parts = dict(zip(order, map(int, match.groups())))
            return date(parts["y"], parts["m"], parts["d"]).isoformat()
    match = re.fullmatch(r"([A-Za-z]+) ([0-9]{1,2}), ([0-9]{4})", value)
    if match:
        month, day, year = match.groups()
    else:
        match = re.fullmatch(r"([0-9]{1,2}) ([A-Za-z]+) ([0-9]{4})", value)
        if not match:
            raise ValueError("invalid date")
        day, month, year = match.groups()
    month_number = MONTHS.get(month.lower())
    if month_number is None:
        raise ValueError("invalid month")
    return date(int(year), month_number, int(day)).isoformat()


def parse_updated(value):
    if not value:
        return datetime.min
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}Z?", value):
        return datetime.min
    try:
        return datetime.strptime(value.rstrip("Z").replace("T", " "), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        # Malformed timestamps, like empty timestamps, cannot establish recency.
        return datetime.min


def clean(input_path, output_path):
    winners = {}
    with open(input_path, encoding="utf-8-sig", newline="") as source:
        rows = records(source)
        header = next(rows, None)
        if header is not None:
            header = [name.strip().lower().replace(" ", "_") for name in header]
            missing = set(FIELDS + ("updated_at",)) - set(header)
            if missing:
                raise ValueError("Missing columns: " + ", ".join(sorted(missing)))
            for values in rows:
                row = {name: value.strip() for name, value in zip(header, values)}
                order_id = row.get("order_id", "").upper()
                if not order_id:
                    continue
                raw_amount = row.get("amount", "")
                try:
                    amount = parse_amount(raw_amount)
                    order_date = parse_date(row.get("order_date", ""))
                except (ValueError, InvalidOperation):
                    continue
                email = row.get("customer_email", "").lower()
                if email.count("@") != 1 or not all(email.split("@")):
                    email = ""
                currency = row.get("currency", "").upper()
                if not currency:
                    currency = next((SYMBOLS[c] for c in raw_amount if c in SYMBOLS), "USD")
                currency = SYMBOLS.get(currency, currency)
                status = row.get("status", "").lower()
                if status == "canceled":
                    status = "cancelled"
                if status not in STATUSES:
                    status = "unknown"
                updated = parse_updated(row.get("updated_at", ""))
                output = (order_id, email, amount, currency, order_date, status)
                if order_id not in winners or updated >= winners[order_id][0]:
                    winners[order_id] = (updated, output)
    with open(output_path, "w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target, lineterminator="\n")
        writer.writerow(FIELDS)
        writer.writerows(sorted((item[1] for item in winners.values()), key=lambda row: (row[4], row[0])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("output")
    args = parser.parse_args()
    clean(args.input, args.output)


if __name__ == "__main__":
    main()
