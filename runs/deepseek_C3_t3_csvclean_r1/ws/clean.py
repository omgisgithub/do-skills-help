#!/usr/bin/env python3
"""Clean a messy order export CSV.

Usage: python3 clean.py INPUT.csv OUTPUT.csv
"""

import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CURRENCY_SYMBOLS = {"$": "USD", "\u20ac": "EUR", "\u00a3": "GBP"}
ALLOWED_STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
FIELDS = [
    "order_id",
    "customer_email",
    "amount",
    "currency",
    "order_date",
    "status",
    "updated_at",
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

UPDATED_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}Z?$")


def normalise_header(name):
    return name.strip().lower().replace(" ", "_")


def clean_email(value):
    value = value.strip().lower()
    if value.count("@") != 1:
        return ""
    local, _, domain = value.partition("@")
    if not local or not domain:
        return ""
    return value


def amount_symbol(value):
    """Return the currency code for the first currency symbol in value."""
    best_code = None
    best_pos = None
    for symbol, code in CURRENCY_SYMBOLS.items():
        pos = value.find(symbol)
        if pos != -1 and (best_pos is None or pos < best_pos):
            best_code = code
            best_pos = pos
    return best_code


def clean_currency(raw_currency, raw_amount):
    cur = raw_currency.strip().upper()
    if cur:
        return CURRENCY_SYMBOLS.get(cur, cur)
    return amount_symbol(raw_amount) or "USD"


def parse_amount(value):
    """Parse an amount string into a Decimal with 2 decimals, or None."""
    s = value.strip()
    if not s:
        return None

    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]

    for symbol in CURRENCY_SYMBOLS:
        s = s.replace(symbol, "")
    s = "".join(s.split())
    if not s:
        return None

    sign = -1 if negative else 1
    if s[0] in "+-":
        if s[0] == "-":
            sign = -sign
        s = s[1:]
    if not s:
        return None

    dots = s.count(".")
    commas = s.count(",")

    if dots and commas:
        if s.rfind(".") > s.rfind(","):
            decimal_sep, thousand_sep = ".", ","
        else:
            decimal_sep, thousand_sep = ",", "."
    elif commas:
        # A comma is a decimal separator only when exactly two digits follow
        # the last one; otherwise it separates thousands.
        if re.search(r",\d{2}$", s):
            decimal_sep, thousand_sep = ",", None
        else:
            decimal_sep, thousand_sep = None, ","
    elif dots:
        decimal_sep, thousand_sep = ".", None
    else:
        decimal_sep, thousand_sep = None, None

    if thousand_sep:
        s = s.replace(thousand_sep, "")

    if decimal_sep:
        if s.count(decimal_sep) != 1:
            return None
        int_part, frac_part = s.split(decimal_sep)
        if not frac_part.isdigit():
            return None
        if not int_part:
            int_part = "0"
        number = int_part + "." + frac_part
    else:
        number = s

    if not re.fullmatch(r"\d+(?:\.\d+)?", number):
        return None

    try:
        result = Decimal(number)
    except InvalidOperation:
        return None
    if not result.is_finite():
        return None

    result = result * sign
    result = result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if result == 0:
        result = abs(result)
    return result


def make_date(year, month, day):
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def month_number(name):
    return MONTHS.get(name.lower())


def parse_date(value):
    """Parse one of the accepted date formats into YYYY-MM-DD, or None."""
    s = value.strip()
    if not s:
        return None

    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return make_date(year, month, day)

    match = re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})", s)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return make_date(year, month, day)

    match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if match:
        day, month, year = (int(part) for part in match.groups())
        return make_date(year, month, day)

    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if match:
        month, day, year = (int(part) for part in match.groups())
        return make_date(year, month, day)

    match = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2})\s*,\s*(\d{4})", s)
    if match:
        name, day, year = match.groups()
        month = month_number(name)
        if month is None:
            return None
        return make_date(int(year), month, int(day))

    match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)
    if match:
        day, name, year = match.groups()
        month = month_number(name)
        if month is None:
            return None
        return make_date(int(year), month, int(day))

    return None


def clean_status(value):
    status = value.strip().lower()
    if status == "canceled":
        status = "cancelled"
    if status not in ALLOWED_STATUSES:
        return "unknown"
    return status


def updated_key(value):
    """Return a comparable datetime; empty/invalid sorts as oldest possible."""
    s = value.strip()
    if not s or not UPDATED_RE.match(s):
        return datetime.min
    if s.endswith("Z"):
        s = s[:-1]
    s = s.replace(" ", "T")
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return datetime.min


def filtered_lines(handle):
    """Yield input lines, skipping blank lines and comment lines."""
    for line in handle:
        if not line.strip():
            continue
        if line.startswith("#"):
            continue
        yield line


def get(row, indexes, name):
    index = indexes.get(name)
    if index is None or index >= len(row):
        return ""
    return row[index]


def read_records(input_path):
    records = {}

    with open(input_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(filtered_lines(handle))
        indexes = None

        for row in reader:
            if not row:
                continue

            if indexes is None:
                indexes = {}
                for position, name in enumerate(row):
                    key = normalise_header(name)
                    if key in FIELDS and key not in indexes:
                        indexes[key] = position
                continue

            order_id = get(row, indexes, "order_id").strip().upper()
            if not order_id:
                continue

            raw_amount = get(row, indexes, "amount")
            amount = parse_amount(raw_amount)
            if amount is None:
                continue

            order_date = parse_date(get(row, indexes, "order_date"))
            if order_date is None:
                continue

            record = {
                "order_id": order_id,
                "customer_email": clean_email(get(row, indexes, "customer_email")),
                "amount": amount,
                "currency": clean_currency(
                    get(row, indexes, "currency"), raw_amount
                ),
                "order_date": order_date,
                "status": clean_status(get(row, indexes, "status")),
                "_updated": updated_key(get(row, indexes, "updated_at")),
            }

            existing = records.get(order_id)
            # >= so that, on a tie, the later row wins.
            if existing is None or record["_updated"] >= existing["_updated"]:
                records[order_id] = record

    return list(records.values())


def write_records(output_path, records):
    records.sort(key=lambda item: (item["order_date"], item["order_id"]))

    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(
            [
                "order_id",
                "customer_email",
                "amount",
                "currency",
                "order_date",
                "status",
            ]
        )
        for record in records:
            writer.writerow(
                [
                    record["order_id"],
                    record["customer_email"],
                    "{0:.2f}".format(record["amount"]),
                    record["currency"],
                    record["order_date"],
                    record["status"],
                ]
            )


def main(argv):
    if len(argv) != 3:
        print("Usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2

    records = read_records(argv[1])
    write_records(argv[2], records)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
