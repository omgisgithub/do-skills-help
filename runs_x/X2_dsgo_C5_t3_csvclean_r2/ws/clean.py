#!/usr/bin/env python3
"""Clean an exported orders CSV.

Usage:
    python3 clean.py INPUT.csv OUTPUT.csv
"""

import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

OUTPUT_FIELDS = [
    "order_id",
    "customer_email",
    "amount",
    "currency",
    "order_date",
    "status",
]

SYMBOL_TO_CURRENCY = {
    "$": "USD",
    "\u20ac": "EUR",  # euro
    "\u00a3": "GBP",  # pound
}

MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sept": 9,
    "sep": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}


def normalize_header(value):
    return value.strip().lower().replace(" ", "_")


def cell(row, indexes, name):
    index = indexes.get(name)
    if index is None or index >= len(row):
        return ""
    return row[index].strip()


def symbol_in(value):
    for character in value:
        if character in SYMBOL_TO_CURRENCY:
            return SYMBOL_TO_CURRENCY[character]
    return None


def parse_amount(value):
    """Return the amount formatted with two decimals, or None if invalid."""
    text = value.strip()
    if not text:
        return None

    for symbol in SYMBOL_TO_CURRENCY:
        text = text.replace(symbol, "")

    # Spaces (including any whitespace) may appear anywhere in the number.
    text = "".join(text.split())
    if not text:
        return None

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    elif "(" in text or ")" in text:
        return None

    if not text or any(character not in "0123456789.," for character in text):
        return None

    has_dot = "." in text
    has_comma = "," in text

    if has_dot and has_comma:
        # Whichever separator appears last is the decimal separator.
        if text.rfind(".") > text.rfind(","):
            decimal_separator = "."
        else:
            decimal_separator = ","
        last_separator = text.rfind(decimal_separator)
        integer_part = re.sub(r"[^0-9]", "", text[:last_separator])
        fractional_part = text[last_separator + 1:]
        text = integer_part + "." + fractional_part
    elif has_comma:
        last_comma = text.rfind(",")
        after = text[last_comma + 1:]
        if len(after) == 2 and after.isdigit():
            text = re.sub(r"[^0-9]", "", text[:last_comma]) + "." + after
        else:
            text = text.replace(",", "")
    # A lone dot is already the decimal separator.

    if not re.fullmatch(r"(?:\d+(?:\.\d*)?|\.\d+)", text):
        return None

    try:
        amount = Decimal(text)
        if negative:
            amount = -amount
        amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None

    return format(amount, ".2f")


def parse_order_date(value):
    """Return YYYY-MM-DD, or None if the date is not an accepted form/valid."""
    text = value.strip()
    if not text:
        return None

    year = month = day = None

    match = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
    if match:
        year, month, day = (int(part) for part in match.groups())
    else:
        match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
        if match:
            day, month, year = (int(part) for part in match.groups())
        else:
            match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
            if match:
                month, day, year = (int(part) for part in match.groups())
            else:
                match = re.fullmatch(
                    r"([A-Za-z]+)\s+(\d{1,2})\s*,\s*(\d{4})", text
                )
                if match:
                    month = MONTHS.get(match.group(1).lower())
                    day = int(match.group(2))
                    year = int(match.group(3))
                    if month is None:
                        return None
                else:
                    match = re.fullmatch(
                        r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text
                    )
                    if not match:
                        return None
                    day = int(match.group(1))
                    month = MONTHS.get(match.group(2).lower())
                    year = int(match.group(3))
                    if month is None:
                        return None

    try:
        return date(year, month, day).isoformat()
    except (TypeError, ValueError):
        return None


def parse_status(value):
    text = value.strip().lower()
    if text == "canceled":
        text = "cancelled"
    if text in {"pending", "paid", "shipped", "cancelled", "refunded"}:
        return text
    return "unknown"


def parse_updated_at(value):
    """Return a datetime for de-duplication; empty/invalid means oldest."""
    text = value.strip()
    if not text:
        return datetime.min

    match = re.fullmatch(
        r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})Z?", text
    )
    if not match:
        return datetime.min

    try:
        return datetime(*(int(part) for part in match.groups()))
    except ValueError:
        return datetime.min


def normalize_email(value):
    text = value.strip().lower()
    if text.count("@") != 1:
        return ""
    local, _, domain = text.partition("@")
    if not local or not domain:
        return ""
    return text


def read_rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        text = handle.read()

    lines = [
        line
        for line in text.splitlines()
        if line.strip() != "" and not line.startswith("#")
    ]
    return csv.reader(lines)


def clean(input_path, output_path):
    reader = read_rows(input_path)

    try:
        header = next(reader)
    except StopIteration:
        header = []

    indexes = {}
    for index, name in enumerate(header):
        normalized = normalize_header(name)
        if normalized:
            indexes.setdefault(normalized, index)

    best = {}

    for row in reader:
        order_id = cell(row, indexes, "order_id").upper()
        if not order_id:
            continue

        amount_text = cell(row, indexes, "amount")
        amount = parse_amount(amount_text)
        if amount is None:
            continue

        order_date = parse_order_date(cell(row, indexes, "order_date"))
        if order_date is None:
            continue

        email = normalize_email(cell(row, indexes, "customer_email"))

        currency = cell(row, indexes, "currency").upper()
        if currency in SYMBOL_TO_CURRENCY:
            currency = SYMBOL_TO_CURRENCY[currency]
        if not currency:
            currency = symbol_in(amount_text) or "USD"

        record = {
            "order_id": order_id,
            "customer_email": email,
            "amount": amount,
            "currency": currency,
            "order_date": order_date,
            "status": parse_status(cell(row, indexes, "status")),
            "_updated_at": parse_updated_at(cell(row, indexes, "updated_at")),
        }

        previous = best.get(order_id)
        # On a tie the later row wins (>=, and rows are processed in order).
        if previous is None or record["_updated_at"] >= previous["_updated_at"]:
            best[order_id] = record

    records = sorted(
        best.values(), key=lambda record: (record["order_date"], record["order_id"])
    )

    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(OUTPUT_FIELDS)
        for record in records:
            writer.writerow([record[field] for field in OUTPUT_FIELDS])


def main(argv):
    if len(argv) != 3:
        print("usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2
    clean(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
