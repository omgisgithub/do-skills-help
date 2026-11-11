#!/usr/bin/env python3
"""Clean an order export CSV.

Usage: python3 clean.py INPUT.csv OUTPUT.csv
"""

import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

REQUIRED_COLUMNS = [
    "order_id",
    "customer_email",
    "amount",
    "currency",
    "order_date",
    "status",
    "updated_at",
]

OUTPUT_COLUMNS = [
    "order_id",
    "customer_email",
    "amount",
    "currency",
    "order_date",
    "status",
]

MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

CURRENCY_SYMBOLS = {"$": "USD", "\u20ac": "EUR", "\u00a3": "GBP"}
STATUS_VALUES = {"pending", "paid", "shipped", "cancelled", "refunded"}

UPDATED_AT_RE = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})Z?"
)
NUMERIC_RE = re.compile(r"(?:\d+(?:\.\d*)?|\.\d+)")


def normalize_header(name):
    return re.sub(r"\s+", "_", name.strip().lower())


def cell(row, indices, name):
    index = indices.get(name)
    if index is None or index >= len(row):
        return ""
    return row[index].strip()


def normalize_email(raw):
    email = raw.strip().lower()
    if email.count("@") != 1:
        return ""
    local, domain = email.split("@", 1)
    if not local or not domain:
        return ""
    return email


def normalize_currency(raw, amount_raw):
    value = raw.strip().upper()
    if not value:
        for char in amount_raw:
            if char in CURRENCY_SYMBOLS:
                return CURRENCY_SYMBOLS[char]
        return "USD"
    if value in CURRENCY_SYMBOLS:
        return CURRENCY_SYMBOLS[value]
    return value


def normalize_status(raw):
    value = raw.strip().lower()
    if value == "canceled":
        return "cancelled"
    if value in STATUS_VALUES:
        return value
    return "unknown"


def parse_amount(raw):
    """Return a Decimal rounded to 2 places, or None if unparseable."""
    text = raw.strip()
    if not text:
        return None

    # Drop currency symbols and all whitespace.
    chars = []
    for char in text:
        if char in CURRENCY_SYMBOLS:
            continue
        if char.isspace():
            continue
        chars.append(char)
    text = "".join(chars)
    if not text:
        return None

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
        if not text:
            return None

    if text[0] in "+-":
        if text[0] == "-":
            negative = not negative
        text = text[1:]
    if not text:
        return None

    # Only digits and decimal/thousands separators are allowed.
    if any(char not in "0123456789.," for char in text):
        return None

    has_dot = "." in text
    has_comma = "," in text

    if has_dot and has_comma:
        if text.rfind(".") > text.rfind(","):
            decimal_sep, thousands_sep = ".", ","
        else:
            decimal_sep, thousands_sep = ",", "."
    elif has_comma:
        digits_after = len(text) - text.rfind(",") - 1
        if digits_after == 2:
            # The last comma is the decimal separator; any earlier commas
            # are thousands separators.
            decimal_sep, thousands_sep = ",", ","
        else:
            decimal_sep, thousands_sep = None, ","
    elif has_dot:
        decimal_sep, thousands_sep = ".", None
    else:
        decimal_sep, thousands_sep = None, None

    if decimal_sep is not None:
        head, _, tail = text.rpartition(decimal_sep)
        if thousands_sep is not None:
            head = head.replace(thousands_sep, "")
            tail = tail.replace(thousands_sep, "")
        text = head + "." + tail
    elif thousands_sep is not None:
        text = text.replace(thousands_sep, "")

    if text.count(".") > 1:
        return None
    if not NUMERIC_RE.fullmatch(text):
        return None

    try:
        with localcontext() as context:
            context.prec = max(50, len(text) + 10)
            value = Decimal(text)
            if negative:
                value = -value
            rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if rounded == 0:
                rounded = abs(rounded)
            return rounded
    except (InvalidOperation, ValueError):
        return None


def make_date(year, month, day):
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_date(raw):
    text = raw.strip()
    if not text:
        return None

    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return make_date(year, month, day)

    match = re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})", text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return make_date(year, month, day)

    match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if match:
        day, month, year = (int(part) for part in match.groups())
        return make_date(year, month, day)

    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if match:
        month, day, year = (int(part) for part in match.groups())
        return make_date(year, month, day)

    match = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2})\s*,\s*(\d{4})", text)
    if match:
        month_name, day, year = match.groups()
        month = MONTHS.get(month_name.lower())
        if month is not None:
            return make_date(int(year), month, int(day))
        return None

    match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text)
    if match:
        day, month_name, year = match.groups()
        month = MONTHS.get(month_name.lower())
        if month is not None:
            return make_date(int(year), month, int(day))
        return None

    return None


def parse_updated_at(raw):
    text = raw.strip()
    if not text:
        return datetime.min
    match = UPDATED_AT_RE.fullmatch(text)
    if not match:
        return datetime.min
    try:
        year, month, day, hour, minute, second = (int(part) for part in match.groups())
        return datetime(year, month, day, hour, minute, second)
    except ValueError:
        return datetime.min


def read_records(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        content = handle.read()

    lines = []
    for line in content.splitlines():
        if not line.strip():
            continue
        if line.startswith("#"):
            continue
        lines.append(line)

    reader = csv.reader(lines)
    try:
        header = next(reader)
    except StopIteration:
        header = []

    indices = {}
    for index, name in enumerate(header):
        key = normalize_header(name)
        if key in REQUIRED_COLUMNS and key not in indices:
            indices[key] = index

    # order_id -> (updated_at, record tuple)
    best = {}

    for row in reader:
        if not row:
            continue

        order_id = cell(row, indices, "order_id").upper()
        if not order_id:
            continue

        amount_raw = cell(row, indices, "amount")
        amount = parse_amount(amount_raw)
        if amount is None:
            continue

        order_date = parse_date(cell(row, indices, "order_date"))
        if order_date is None:
            continue

        record = (
            order_id,
            normalize_email(cell(row, indices, "customer_email")),
            format(amount, ".2f"),
            normalize_currency(cell(row, indices, "currency"), amount_raw),
            order_date.isoformat(),
            normalize_status(cell(row, indices, "status")),
        )
        updated_at = parse_updated_at(cell(row, indices, "updated_at"))

        previous = best.get(order_id)
        # ">=" makes a tie keep the row that appears later in the file.
        if previous is None or updated_at >= previous[0]:
            best[order_id] = (updated_at, record)

    records = [entry[1] for entry in best.values()]
    records.sort(key=lambda record: (record[4], record[0]))
    return records


def write_records(path, records):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(OUTPUT_COLUMNS)
        writer.writerows(records)


def main(argv):
    if len(argv) != 3:
        print("usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2

    records = read_records(argv[1])
    write_records(argv[2], records)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
