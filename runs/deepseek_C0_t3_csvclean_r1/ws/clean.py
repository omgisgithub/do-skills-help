#!/usr/bin/env python3
"""Clean a raw order export CSV.

Usage:
    python3 clean.py INPUT.csv OUTPUT.csv
"""

import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, getcontext

getcontext().prec = 100

OUTPUT_COLUMNS = [
    "order_id",
    "customer_email",
    "amount",
    "currency",
    "order_date",
    "status",
]

SYMBOLS = {"$": "USD", "\u20ac": "EUR", "\u00a3": "GBP"}
SYMBOL_PATTERN = re.compile(r"[$€£]")
ALLOWED_STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
SLASH_YMD_RE = re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})$")
DOTTED_DMY_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")
SLASH_MDY_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
MONTH_FIRST_RE = re.compile(r"^([A-Za-z]+)\s+(\d{1,2})\s*,\s*(\d{4})$")
DAY_FIRST_RE = re.compile(r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$")
NUMBER_RE = re.compile(r"^(?:\d+(?:\.\d*)?|\.\d+)$")
UPDATED_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})[Zz]?$"
)


def normalise_header(name):
    return name.strip().lower().replace(" ", "_")


def parse_amount(value):
    """Return (Decimal amount, symbol currency or None), or None if invalid."""
    text = value.strip()
    if not text:
        return None

    symbol_match = SYMBOL_PATTERN.search(text)
    symbol = symbol_match.group(0) if symbol_match else None

    # Remove currency symbols and whitespace wherever they appear.
    body = SYMBOL_PATTERN.sub("", text)
    body = re.sub(r"\s+", "", body)
    if not body:
        return None

    negative = False
    if body.startswith("(") and body.endswith(")"):
        negative = True
        body = body[1:-1]
    elif body.startswith(("+", "-")):
        if body[0] == "-":
            negative = True
        body = body[1:]

    if not body:
        return None

    if "." in body and "," in body:
        if body.rfind(".") > body.rfind(","):
            decimal_sep, thousands_sep = ".", ","
        else:
            decimal_sep, thousands_sep = ",", "."
        body = body.replace(thousands_sep, "")
        body = body.replace(decimal_sep, ".")
    elif "," in body:
        last_comma = body.rfind(",")
        tail = body[last_comma + 1:]
        if re.fullmatch(r"\d{2}", tail):
            # The last comma is the decimal separator; any earlier ones are
            # thousands separators.
            body = body[:last_comma].replace(",", "") + "." + tail
        else:
            body = body.replace(",", "")

    if not NUMBER_RE.fullmatch(body):
        return None

    try:
        amount = Decimal(body)
    except InvalidOperation:
        return None

    if negative:
        amount = -amount

    try:
        amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None

    if amount == 0:
        amount = Decimal("0.00")

    return amount, symbol


def parse_order_date(value):
    """Return a date, or None if the value is missing/invalid."""
    text = value.strip()
    if not text:
        return None

    year = month = day = None

    match = ISO_DATE_RE.fullmatch(text)
    if match:
        year, month, day = (int(part) for part in match.groups())
    else:
        match = SLASH_YMD_RE.fullmatch(text)
        if match:
            year, month, day = (int(part) for part in match.groups())
        else:
            match = DOTTED_DMY_RE.fullmatch(text)
            if match:
                day, month, year = (int(part) for part in match.groups())
            else:
                match = SLASH_MDY_RE.fullmatch(text)
                if match:
                    month, day, year = (int(part) for part in match.groups())
                else:
                    match = MONTH_FIRST_RE.fullmatch(text)
                    if match:
                        month_name, day_text, year_text = match.groups()
                        month = MONTHS.get(month_name.lower())
                        day = int(day_text)
                        year = int(year_text)
                    else:
                        match = DAY_FIRST_RE.fullmatch(text)
                        if match:
                            day_text, month_name, year_text = match.groups()
                            day = int(day_text)
                            month = MONTHS.get(month_name.lower())
                            year = int(year_text)
                        else:
                            return None

    if month is None:
        return None

    try:
        return date(year, month, day)
    except ValueError:
        return None


def normalise_status(value):
    status = value.strip().lower()
    if status == "canceled":
        status = "cancelled"
    if status in ALLOWED_STATUSES:
        return status
    return "unknown"


def normalise_currency(value, amount_symbol):
    currency = value.strip().upper()
    if currency:
        return SYMBOLS.get(currency, currency)
    if amount_symbol:
        return SYMBOLS[amount_symbol]
    return "USD"


def normalise_email(value):
    email = value.strip().lower()
    if email.count("@") != 1:
        return ""
    local, domain = email.split("@")
    if not local or not domain:
        return ""
    return email


def parse_updated_at(value):
    """Return a comparable datetime; missing/invalid means oldest possible."""
    text = value.strip()
    match = UPDATED_RE.fullmatch(text)
    if not match:
        return datetime.min
    try:
        return datetime(*(int(part) for part in match.groups()))
    except ValueError:
        return datetime.min


def main(argv):
    if len(argv) != 3:
        print("usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2

    input_path, output_path = argv[1], argv[2]

    with open(input_path, "r", encoding="utf-8-sig", newline="") as handle:
        text = handle.read()

    lines = [
        line
        for line in text.splitlines()
        if line.strip() and not line.startswith("#")
    ]

    reader = csv.reader(lines)
    try:
        header = next(reader)
    except StopIteration:
        header = []

    indices = {}
    for index, name in enumerate(header):
        key = normalise_header(name)
        if key in OUTPUT_COLUMNS and key not in indices:
            indices[key] = index

    def field(row, name):
        index = indices.get(name)
        if index is None or index >= len(row):
            return ""
        return row[index]

    rows = {}
    for row in reader:
        order_id = field(row, "order_id").strip().upper()
        if not order_id:
            continue

        amount_result = parse_amount(field(row, "amount"))
        if amount_result is None:
            continue
        amount, amount_symbol = amount_result

        order_date = parse_order_date(field(row, "order_date"))
        if order_date is None:
            continue

        updated_at = parse_updated_at(field(row, "updated_at"))

        record = {
            "order_id": order_id,
            "customer_email": normalise_email(field(row, "customer_email")),
            "amount": format(amount, ".2f"),
            "currency": normalise_currency(
                field(row, "currency"), amount_symbol
            ),
            "order_date": order_date.isoformat(),
            "status": normalise_status(field(row, "status")),
            "_updated_at": updated_at,
        }

        previous = rows.get(order_id)
        if previous is None or updated_at >= previous["_updated_at"]:
            rows[order_id] = record

    output_rows = sorted(
        rows.values(), key=lambda item: (item["order_date"], item["order_id"])
    )

    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(OUTPUT_COLUMNS)
        for record in output_rows:
            writer.writerow([record[column] for column in OUTPUT_COLUMNS])

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
