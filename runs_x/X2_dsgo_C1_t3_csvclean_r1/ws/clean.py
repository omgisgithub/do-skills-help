#!/usr/bin/env python3
"""Clean a shop order export CSV.

Usage:
    python3 clean.py INPUT.csv OUTPUT.csv
"""

import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

FIELDS = [
    "order_id",
    "customer_email",
    "amount",
    "currency",
    "order_date",
    "status",
    "updated_at",
]

STATUS_MAP = {
    "pending": "pending",
    "paid": "paid",
    "shipped": "shipped",
    "canceled": "cancelled",
    "cancelled": "cancelled",
    "refunded": "refunded",
}

CURRENCY_SYMBOLS = {
    "$": "USD",
    "\u20ac": "EUR",  # euro
    "\u00a3": "GBP",  # pound
}

MONTH_NAMES = {
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

MIN_TIMESTAMP = datetime.min


def normalise_header(name):
    return name.strip().lower().replace(" ", "_")


def clean_email(value):
    email = value.strip().lower()
    if email.count("@") != 1:
        return ""
    local, _, domain = email.partition("@")
    if not local or not domain:
        return ""
    return email


def parse_amount(raw):
    """Return the amount formatted with two decimals, or None if unparseable."""
    text = raw.strip()
    if not text:
        return None

    # Strip currency symbols and all whitespace (they may appear anywhere).
    text = re.sub(r"[\s$\u20ac\u00a3]", "", text)
    if not text:
        return None

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    elif "(" in text or ")" in text:
        return None

    if text.startswith("-"):
        negative = not negative
        text = text[1:]
    elif text.startswith("+"):
        text = text[1:]

    if not text:
        return None

    has_dot = "." in text
    has_comma = "," in text

    if has_dot and has_comma:
        if text.rfind(".") > text.rfind(","):
            decimal_sep, thousands_sep = ".", ","
        else:
            decimal_sep, thousands_sep = ",", "."
    elif has_comma:
        last_comma = text.rfind(",")
        if len(text) - last_comma - 1 == 2:
            decimal_sep, thousands_sep = ",", None
        else:
            decimal_sep, thousands_sep = None, ","
    elif has_dot:
        decimal_sep, thousands_sep = ".", None
    else:
        decimal_sep, thousands_sep = None, None

    if thousands_sep:
        text = text.replace(thousands_sep, "")
    if decimal_sep and decimal_sep != ".":
        text = text.replace(decimal_sep, ".")

    if not re.fullmatch(r"(?:\d+(?:\.\d*)?|\.\d+)", text):
        return None

    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    if not value.is_finite():
        return None

    if negative:
        value = -value

    value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if value == 0:
        value = abs(value)  # avoid "-0.00"
    return format(value, ".2f")


def amount_currency_symbol(raw):
    """Return the currency code indicated by the first symbol in the amount."""
    for char in raw:
        if char in CURRENCY_SYMBOLS:
            return CURRENCY_SYMBOLS[char]
    return None


def clean_currency(raw, amount_raw):
    currency = raw.strip()
    if currency:
        if currency in CURRENCY_SYMBOLS:
            return CURRENCY_SYMBOLS[currency]
        return currency.upper()
    return amount_currency_symbol(amount_raw) or "USD"


def month_number(name):
    return MONTH_NAMES.get(name.rstrip(".").lower())


def make_date(year, month, day):
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_date(raw):
    """Return a date, or None if the value is not an accepted/valid date."""
    text = raw.strip()
    if not text:
        return None

    # 2026-03-04 / 2026/03/04 (same separator required)
    match = re.fullmatch(r"(\d{4})([-/])(\d{1,2})\2(\d{1,2})", text)
    if match:
        return make_date(int(match.group(1)), int(match.group(3)), int(match.group(4)))

    # 04.03.2026 (day.month.year)
    match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if match:
        return make_date(int(match.group(3)), int(match.group(2)), int(match.group(1)))

    # 03/04/2026 (month/day/year)
    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if match:
        return make_date(int(match.group(3)), int(match.group(1)), int(match.group(2)))

    # Mar 4, 2026 / March 4, 2026
    match = re.fullmatch(r"([A-Za-z]+\.?)\s+(\d{1,2}),\s*(\d{4})", text)
    if match:
        month = month_number(match.group(1))
        if month is None:
            return None
        return make_date(int(match.group(3)), month, int(match.group(2)))

    # 4 Mar 2026 / 4 March 2026
    match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+\.?)\s+(\d{4})", text)
    if match:
        month = month_number(match.group(2))
        if month is None:
            return None
        return make_date(int(match.group(3)), month, int(match.group(1)))

    return None


def clean_status(raw):
    status = raw.strip().lower()
    return STATUS_MAP.get(status, "unknown")


def parse_updated_at(raw):
    text = raw.strip()
    if not text:
        return MIN_TIMESTAMP
    if text.endswith("Z"):
        text = text[:-1]
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return MIN_TIMESTAMP


def read_rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        lines = handle.read().splitlines()

    kept = [
        line
        for line in lines
        if line.strip() != "" and not line.startswith("#")
    ]
    return list(csv.reader(kept))


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: python3 clean.py INPUT.csv OUTPUT.csv\n")
        return 2

    input_path, output_path = argv[1], argv[2]
    reader = read_rows(input_path)
    if not reader:
        rows_out = []
    else:
        header = [normalise_header(name) for name in reader[0]]
        index = {}
        for position, name in enumerate(header):
            if name in FIELDS and name not in index:
                index[name] = position

        def value(row, field):
            position = index.get(field)
            if position is None or position >= len(row):
                return ""
            return row[position]

        cleaned = []
        for row in reader[1:]:
            order_id = value(row, "order_id").strip().upper()
            if not order_id:
                continue

            amount = parse_amount(value(row, "amount"))
            if amount is None:
                continue

            order_date = parse_date(value(row, "order_date"))
            if order_date is None:
                continue

            cleaned.append(
                {
                    "order_id": order_id,
                    "customer_email": clean_email(value(row, "customer_email")),
                    "amount": amount,
                    "currency": clean_currency(
                        value(row, "currency"), value(row, "amount")
                    ),
                    "order_date": order_date.isoformat(),
                    "status": clean_status(value(row, "status")),
                    "updated_at": parse_updated_at(value(row, "updated_at")),
                }
            )

        # De-duplicate: latest updated_at wins; ties go to the later row.
        best = {}
        order = []
        for record in cleaned:
            key = record["order_id"]
            if key not in best:
                best[key] = record
                order.append(key)
            elif record["updated_at"] >= best[key]["updated_at"]:
                best[key] = record

        rows_out = [best[key] for key in order]
        rows_out.sort(key=lambda record: (record["order_date"], record["order_id"]))

    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(
            ["order_id", "customer_email", "amount", "currency", "order_date", "status"]
        )
        for record in rows_out:
            writer.writerow(
                [
                    record["order_id"],
                    record["customer_email"],
                    record["amount"],
                    record["currency"],
                    record["order_date"],
                    record["status"],
                ]
            )

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
