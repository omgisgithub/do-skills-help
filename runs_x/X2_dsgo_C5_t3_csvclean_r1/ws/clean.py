#!/usr/bin/env python3
"""Clean a shop order export CSV.

Usage: python3 clean.py INPUT.csv OUTPUT.csv
"""

import calendar
import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

OUTPUT_HEADER = [
    "order_id",
    "customer_email",
    "amount",
    "currency",
    "order_date",
    "status",
]

STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}

SYMBOL_CURRENCY = {"$": "USD", "\u20ac": "EUR", "\u00a3": "GBP"}

MONTHS = {}
for _month in range(1, 13):
    MONTHS[calendar.month_name[_month].lower()] = _month
    MONTHS[calendar.month_abbr[_month].lower()] = _month
MONTHS["sept"] = 9

UPDATED_RE = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})[Zz]?"
)


def normalize_header(value):
    return value.strip().lower().replace(" ", "_")


def clean_email(value):
    email = value.strip().lower()
    if email.count("@") != 1:
        return ""
    local, domain = email.split("@")
    if local and domain:
        return email
    return ""


def parse_amount(value):
    """Return (Decimal or None, currency code or None)."""
    original = value.strip()
    if not original:
        return None, None

    symbol_currency = None
    for ch in original:
        if ch in SYMBOL_CURRENCY:
            symbol_currency = SYMBOL_CURRENCY[ch]
            break

    # Remove currency symbols and all whitespace before deciding about signs.
    text = "".join(
        ch for ch in original if ch not in SYMBOL_CURRENCY and not ch.isspace()
    )

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    if text.startswith("-"):
        negative = not negative
        text = text[1:]
    elif text.startswith("+"):
        text = text[1:]

    if not text or not re.fullmatch(r"[0-9.,]+", text):
        return None, symbol_currency
    if not any(ch.isdigit() for ch in text):
        return None, symbol_currency

    has_dot = "." in text
    has_comma = "," in text

    if has_dot and has_comma:
        decimal_sep = "." if text.rfind(".") > text.rfind(",") else ","
        thousands_sep = "," if decimal_sep == "." else "."
        if text.count(decimal_sep) != 1:
            return None, symbol_currency
        text = text.replace(thousands_sep, "").replace(decimal_sep, ".")
    elif has_comma:
        # If exactly two digits follow the last comma, it is the decimal mark.
        if re.search(r",\d{2}$", text):
            last_comma = text.rfind(",")
            text = text[:last_comma].replace(",", "") + "." + text[last_comma + 1:]
        else:
            text = text.replace(",", "")
    elif has_dot:
        if text.count(".") != 1:
            return None, symbol_currency

    if not re.fullmatch(r"\d+(\.\d+)?", text):
        return None, symbol_currency

    try:
        amount = Decimal(text)
        if negative:
            amount = -amount
        with localcontext() as ctx:
            ctx.prec = 60
            amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None, symbol_currency

    if amount == 0:
        amount = abs(amount)
    return amount, symbol_currency


def format_amount(amount):
    return format(amount, "f")


def safe_date(year, month, day):
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_date(value):
    text = value.strip()
    if not text:
        return None

    # Year first: 2026-03-04 and 2026/03/04
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return safe_date(year, month, day)

    match = re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})", text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return safe_date(year, month, day)

    # Day first: 04.03.2026
    match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if match:
        day, month, year = (int(part) for part in match.groups())
        return safe_date(year, month, day)

    # Month first: 03/04/2026
    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if match:
        month, day, year = (int(part) for part in match.groups())
        return safe_date(year, month, day)

    # Month name first: Mar 4, 2026 / March 4, 2026
    match = re.fullmatch(r"([A-Za-z]+)\.?\s+(\d{1,2})\s*,\s*(\d{4})", text)
    if match:
        month = MONTHS.get(match.group(1).lower())
        if month is not None:
            day = int(match.group(2))
            year = int(match.group(3))
            return safe_date(year, month, day)

    # Day first with month name: 4 Mar 2026 / 4 March 2026
    match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\.?\s+(\d{4})", text)
    if match:
        month = MONTHS.get(match.group(2).lower())
        if month is not None:
            day = int(match.group(1))
            year = int(match.group(3))
            return safe_date(year, month, day)

    return None


def clean_status(value):
    status = value.strip().lower()
    if status == "canceled":
        status = "cancelled"
    if status in STATUSES:
        return status
    return "unknown"


def parse_updated_at(value):
    text = value.strip()
    if not text:
        return datetime.min
    match = UPDATED_RE.fullmatch(text)
    if not match:
        return datetime.min
    try:
        return datetime(*((int(part) for part in match.groups())))
    except ValueError:
        return datetime.min


def read_rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        text = handle.read()

    lines = []
    for line in text.splitlines():
        if line.strip() == "":
            continue
        if line.startswith("#"):
            continue
        lines.append(line)
    return lines


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: python3 clean.py INPUT.csv OUTPUT.csv\n")
        return 2

    input_path, output_path = argv[1], argv[2]
    lines = read_rows(input_path)

    header = []
    rows = []
    if lines:
        reader = csv.reader(lines)
        header = [normalize_header(name) for name in next(reader, [])]
        rows = list(reader)

    indexes = {}
    for index, name in enumerate(header):
        if name and name not in indexes:
            indexes[name] = index

    def cell(row, column):
        index = indexes.get(column)
        if index is None or index >= len(row):
            return ""
        return row[index]

    # order_id -> (updated_at, output record)
    kept = {}

    for row in rows:
        order_id = cell(row, "order_id").strip().upper()
        if not order_id:
            continue

        amount, symbol_currency = parse_amount(cell(row, "amount"))
        if amount is None:
            continue

        order_date = parse_date(cell(row, "order_date"))
        if order_date is None:
            continue

        email = clean_email(cell(row, "customer_email"))

        raw_currency = cell(row, "currency").strip().upper()
        if raw_currency:
            currency = SYMBOL_CURRENCY.get(raw_currency, raw_currency)
        else:
            currency = symbol_currency or "USD"

        status = clean_status(cell(row, "status"))
        updated_at = parse_updated_at(cell(row, "updated_at"))

        record = (
            order_id,
            email,
            format_amount(amount),
            currency,
            order_date.isoformat(),
            status,
        )

        previous = kept.get(order_id)
        # On a tie the later row (processed later) wins.
        if previous is None or updated_at >= previous[0]:
            kept[order_id] = (updated_at, record)

    records = sorted(
        (entry[1] for entry in kept.values()),
        key=lambda record: (record[4], record[0]),
    )

    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(OUTPUT_HEADER)
        writer.writerows(records)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
