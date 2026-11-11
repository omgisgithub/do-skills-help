#!/usr/bin/env python3
"""Normalize a messy order export into the shop's canonical CSV format."""

import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
import sys


OUTPUT_FIELDS = (
    "order_id",
    "customer_email",
    "amount",
    "currency",
    "order_date",
    "status",
)
ALLOWED_STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
SYMBOL_CURRENCIES = {"$": "USD", "€": "EUR", "£": "GBP"}


def normalize_header(value):
    return value.strip().lower().replace(" ", "_")


def parse_amount(value):
    """Return (formatted_amount, currency_symbol), or (None, symbol)."""
    value = value.strip()
    symbol = next((s for s in SYMBOL_CURRENCIES if s in value), "")
    text = value
    for s in SYMBOL_CURRENCIES:
        text = text.replace(s, "")
    text = re.sub(r"\s+", "", text)
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    elif "(" in text or ")" in text:
        return None, symbol
    if not text or not re.fullmatch(r"[+-]?[0-9.,]+", text):
        return None, symbol

    if "." in text and "," in text:
        decimal_mark = "." if text.rfind(".") > text.rfind(",") else ","
        thousands_mark = "," if decimal_mark == "." else "."
        text = text.replace(thousands_mark, "").replace(decimal_mark, ".")
    elif "," in text:
        if re.search(r",\d{2}$", text):
            last_comma = text.rfind(",")
            text = text[:last_comma].replace(",", "") + "." + text[last_comma + 1 :]
        else:
            text = text.replace(",", "")
    # With only periods, periods are decimal marks. Permit one only.
    if text.count(".") > 1:
        return None, symbol
    try:
        amount = Decimal(text)
        if negative:
            amount = -amount
        formatted = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None, symbol
    return format(formatted, ".2f"), symbol


def parse_date(value):
    value = value.strip()
    patterns = (
        (r"\d{4}-\d{1,2}-\d{1,2}", "%Y-%m-%d"),
        (r"\d{4}/\d{1,2}/\d{1,2}", "%Y/%m/%d"),
        (r"\d{1,2}\.\d{1,2}\.\d{4}", "%d.%m.%Y"),
        (r"\d{1,2}/\d{1,2}/\d{4}", "%m/%d/%Y"),
    )
    for pattern, fmt in patterns:
        if re.fullmatch(pattern, value):
            try:
                return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
            except ValueError:
                return None
    month = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    match = re.fullmatch(rf"({month}) (\d{{1,2}}), (\d{{4}})", value, re.IGNORECASE)
    if match:
        try:
            parsed = datetime.strptime(match.group(1)[:3].title() + " " + match.group(2) + " " + match.group(3), "%b %d %Y")
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            return None
    match = re.fullmatch(rf"(\d{{1,2}}) ({month}) (\d{{4}})", value, re.IGNORECASE)
    if match:
        try:
            parsed = datetime.strptime(match.group(1) + " " + match.group(2)[:3].title() + " " + match.group(3), "%d %b %Y")
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None


def updated_key(value, sequence):
    value = value.strip()
    if not value:
        return (0, "", sequence)
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(Z?)", value)
    if not match:
        return (0, "", sequence)
    try:
        stamp = datetime.strptime(match.group(1) + " " + match.group(2), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return (0, "", sequence)
    return (1, stamp, sequence)


def clean(input_path, output_path):
    with open(input_path, "r", encoding="utf-8-sig", newline="") as source:
        lines = (line for line in source if line.strip() and not line.startswith("#"))
        reader = csv.reader(lines)
        try:
            header = next(reader)
        except StopIteration:
            header = []
            rows = []
        else:
            positions = {normalize_header(name): i for i, name in enumerate(header)}
            rows = []
            best = {}
            for sequence, values in enumerate(reader):
                def get(name):
                    index = positions.get(name)
                    return values[index].strip() if index is not None and index < len(values) else ""

                order_id = get("order_id").upper()
                amount, symbol = parse_amount(get("amount"))
                order_date = parse_date(get("order_date"))
                if not order_id or amount is None or order_date is None:
                    continue
                email = get("customer_email").lower()
                if email.count("@") != 1 or not all(email.split("@")):
                    email = ""
                currency = get("currency").upper()
                if currency in SYMBOL_CURRENCIES:
                    currency = SYMBOL_CURRENCIES[currency]
                if not currency:
                    currency = SYMBOL_CURRENCIES.get(symbol, "USD")
                status = get("status").lower()
                if status == "canceled":
                    status = "cancelled"
                if status not in ALLOWED_STATUSES:
                    status = "unknown"
                row = {
                    "order_id": order_id,
                    "customer_email": email,
                    "amount": amount,
                    "currency": currency,
                    "order_date": order_date,
                    "status": status,
                }
                key = updated_key(get("updated_at"), sequence)
                old = best.get(order_id)
                if old is None or key > old[0]:
                    best[order_id] = (key, row)
            rows = [item[1] for item in best.values()]

    rows.sort(key=lambda row: (row["order_date"], row["order_id"]))
    with open(output_path, "w", encoding="utf-8", newline="") as destination:
        writer = csv.writer(destination, lineterminator="\n")
        writer.writerow(OUTPUT_FIELDS)
        for row in rows:
            writer.writerow([row[field] for field in OUTPUT_FIELDS])


def main(argv):
    if len(argv) != 3:
        print("Usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2
    clean(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
