#!/usr/bin/env python3
"""Clean a shop order export CSV."""

import csv
import io
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

ALLOWED_STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}

SYMBOL_CURRENCIES = {"$": "USD", "\u20ac": "EUR", "\u00a3": "GBP"}

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
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def normalise_header(name):
    return (name or "").strip().lower().replace(" ", "_")


def parse_amount(raw):
    """Return a Decimal rounded to 2 places, or None if unparseable."""
    text = (raw or "").strip()
    if not text:
        return None

    negative = False
    if "(" in text or ")" in text:
        # Accounting negatives are wrapped in parentheses.
        if "(" not in text or ")" not in text:
            return None
        negative = True
        text = text.replace("(", "").replace(")", "")

    text = re.sub(r"\s+", "", text)
    for symbol in SYMBOL_CURRENCIES:
        text = text.replace(symbol, "")

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
            # Last separator is the decimal point.
            digits = text.replace(",", "")
        else:
            # Last separator is the decimal comma.
            index = text.rfind(",")
            digits = text[:index].replace(",", "").replace(".", "")
            digits += "." + text[index + 1:]
    elif has_comma:
        tail = text[text.rfind(",") + 1:]
        if len(tail) == 2 and tail.isdigit():
            index = text.rfind(",")
            digits = text[:index].replace(",", "").replace(".", "")
            digits += "." + text[index + 1:]
        else:
            digits = text.replace(",", "")
    elif has_dot:
        digits = text
    else:
        digits = text

    if not re.fullmatch(r"\d+(?:\.\d+)?", digits):
        return None

    try:
        value = Decimal(digits)
    except InvalidOperation:
        return None

    if negative:
        value = -value
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def parse_date(raw):
    """Return a date object, or None if missing/invalid."""
    text = (raw or "").strip()
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

    # "Mar 4, 2026" or "March 4, 2026" (comma required)
    match = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})", text)
    if match:
        month_name, day, year = match.groups()
        month = MONTHS.get(month_name.lower())
        if month is not None:
            return make_date(int(year), month, int(day))

    # "4 Mar 2026" or "4 March 2026" (no comma)
    match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text)
    if match:
        day, month_name, year = match.groups()
        month = MONTHS.get(month_name.lower())
        if month is not None:
            return make_date(int(year), month, int(day))

    return None


def make_date(year, month, day):
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_updated_at(raw):
    """Return a datetime for ordering, or datetime.min when empty/invalid."""
    text = (raw or "").strip()
    match = re.fullmatch(
        r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})Z?", text
    )
    if not match:
        return datetime.min
    try:
        return datetime(*(int(part) for part in match.groups()))
    except ValueError:
        return datetime.min


def normalise_email(raw):
    email = (raw or "").strip().lower()
    if email.count("@") != 1:
        return ""
    local, domain = email.split("@")
    if not local or not domain:
        return ""
    return email


def normalise_currency(raw_currency, raw_amount):
    currency = (raw_currency or "").strip().upper()
    if currency:
        return SYMBOL_CURRENCIES.get(currency, currency)

    for character in raw_amount or "":
        if character in SYMBOL_CURRENCIES:
            return SYMBOL_CURRENCIES[character]
    return "USD"


def normalise_status(raw):
    status = (raw or "").strip().lower()
    if status == "canceled":
        status = "cancelled"
    if status not in ALLOWED_STATUSES:
        return "unknown"
    return status


def read_rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        text = handle.read()

    lines = []
    for line in text.splitlines(keepends=True):
        if line.strip() == "":
            continue
        if line[0] == "#":
            continue
        lines.append(line)

    return list(csv.reader(io.StringIO("".join(lines))))


def clean(input_path, output_path):
    rows = read_rows(input_path)

    if not rows:
        header = []
        data_rows = []
    else:
        header = [normalise_header(name) for name in rows[0]]
        data_rows = rows[1:]

    positions = {}
    for index, name in enumerate(header):
        if name in FIELDS and name not in positions:
            positions[name] = index

    best = {}
    for line_number, row in enumerate(data_rows):
        def value(field):
            index = positions.get(field)
            if index is None or index >= len(row):
                return ""
            return row[index]

        order_id = value("order_id").strip().upper()
        if not order_id:
            continue

        raw_amount = value("amount").strip()
        amount = parse_amount(raw_amount)
        if amount is None:
            continue

        order_date = parse_date(value("order_date"))
        if order_date is None:
            continue

        key = (parse_updated_at(value("updated_at")), line_number)
        if order_id not in best or key > best[order_id][0]:
            best[order_id] = (
                key,
                [
                    order_id,
                    normalise_email(value("customer_email")),
                    format(amount, ".2f"),
                    normalise_currency(value("currency"), raw_amount),
                    order_date.isoformat(),
                    normalise_status(value("status")),
                ],
            )

    output_rows = sorted(
        (entry[1] for entry in best.values()),
        key=lambda record: (record[4], record[0]),
    )

    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(
            ["order_id", "customer_email", "amount", "currency", "order_date", "status"]
        )
        writer.writerows(output_rows)


def main(argv):
    if len(argv) != 3:
        print("usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2
    clean(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
