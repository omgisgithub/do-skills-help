#!/usr/bin/env python3
"""Clean an order export CSV.

Usage: python3 clean.py INPUT.csv OUTPUT.csv
"""

import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

FIELDS = (
    "order_id",
    "customer_email",
    "amount",
    "currency",
    "order_date",
    "status",
    "updated_at",
)

OUTPUT_FIELDS = (
    "order_id",
    "customer_email",
    "amount",
    "currency",
    "order_date",
    "status",
)

STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}

CURRENCY_SYMBOLS = {"$": "USD", "\u20ac": "EUR", "\u00a3": "GBP"}

MONTH_NAMES = {}
for _number, _name in enumerate(
    (
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    ),
    start=1,
):
    MONTH_NAMES[_name] = _number
    MONTH_NAMES[_name[:3]] = _number
MONTH_NAMES["sept"] = 9


def normalise_header(name):
    return re.sub(r"\s+", "_", name.strip().lower())


def normalise_email(value):
    email = value.strip().lower()
    if email.count("@") != 1:
        return ""
    local, domain = email.split("@", 1)
    if not local or not domain:
        return ""
    return email


def symbol_in(value):
    for symbol in CURRENCY_SYMBOLS:
        if symbol in value:
            return CURRENCY_SYMBOLS[symbol]
    return None


def parse_amount(value):
    """Return a Decimal rounded to two places, or None if unparseable."""
    text = re.sub(r"\s+", "", value)

    # Remove currency symbols wherever they occur.
    for symbol in CURRENCY_SYMBOLS:
        text = text.replace(symbol, "")

    if not text:
        return None

    negative = False

    # Accounting negatives: (12.50), ($12.50), -(12.50), (-12.50), ...
    changed = True
    while changed:
        changed = False
        if text.startswith("-"):
            negative = True
            text = text[1:]
            changed = True
        elif text.startswith("+"):
            text = text[1:]
            changed = True
        if text.startswith("(") and text.endswith(")"):
            negative = True
            text = text[1:-1]
            changed = True

    if not text or not re.fullmatch(r"[0-9.,]+", text):
        return None

    has_dot = "." in text
    has_comma = "," in text

    if has_dot and has_comma:
        if text.rfind(".") > text.rfind(","):
            decimal_sep = "."
        else:
            decimal_sep = ","
    elif has_comma:
        tail = text.rsplit(",", 1)[1]
        decimal_sep = "," if (len(tail) == 2 and tail.isdigit()) else None
    elif has_dot:
        decimal_sep = "."
    else:
        decimal_sep = None

    if decimal_sep == ",":
        head, _, tail = text.rpartition(",")
        head = head.replace(",", "").replace(".", "")
        number_text = head + "." + tail
    elif decimal_sep == ".":
        number_text = text.replace(",", "")
    else:
        number_text = text.replace(",", "").replace(".", "")

    if not re.fullmatch(r"[0-9]*\.?[0-9]*", number_text):
        return None
    if not any(ch.isdigit() for ch in number_text):
        return None

    try:
        amount = Decimal(number_text)
    except InvalidOperation:
        return None

    if negative:
        amount = -amount

    try:
        amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None

    if amount == 0:
        amount = abs(amount)
    return amount


def make_date(year, month, day):
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_date(value):
    text = value.strip()
    if not text:
        return None

    # YYYY-MM-DD / YYYY/MM/DD
    match = re.fullmatch(r"(\d{4})([-/])(\d{1,2})\2(\d{1,2})", text)
    if match:
        return make_date(int(match.group(1)), int(match.group(3)), int(match.group(4)))

    # DD.MM.YYYY
    match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if match:
        return make_date(int(match.group(3)), int(match.group(2)), int(match.group(1)))

    # MM/DD/YYYY
    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if match:
        return make_date(int(match.group(3)), int(match.group(1)), int(match.group(2)))

    # Mar 4, 2026 / March 4, 2026
    match = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", text)
    if match:
        month = MONTH_NAMES.get(match.group(1).lower())
        if month is None:
            return None
        return make_date(int(match.group(3)), month, int(match.group(2)))

    # 4 Mar 2026 / 4 March 2026
    match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text)
    if match:
        month = MONTH_NAMES.get(match.group(2).lower())
        if month is None:
            return None
        return make_date(int(match.group(3)), month, int(match.group(1)))

    return None


def parse_updated_at(value):
    """Return a comparable datetime; empty or invalid means oldest possible."""
    text = value.strip()
    if not text:
        return datetime.min

    match = re.fullmatch(
        r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})Z?", text
    )
    if not match:
        return datetime.min

    try:
        return datetime(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
            int(match.group(4)),
            int(match.group(5)),
            int(match.group(6)),
        )
    except ValueError:
        return datetime.min


def normalise_status(value):
    status = value.strip().lower()
    if status == "canceled":
        status = "cancelled"
    if status in STATUSES:
        return status
    return "unknown"


def get_value(row, indices, name):
    index = indices.get(name)
    if index is None or index >= len(row):
        return ""
    return row[index]


def read_records(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        text = handle.read()

    lines = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith("#"):
            continue
        lines.append(line)

    reader = csv.reader(lines, skipinitialspace=True)
    header = next(reader, None)
    if header is None:
        return []

    indices = {}
    for index, name in enumerate(header):
        key = normalise_header(name)
        if key in FIELDS and key not in indices:
            indices[key] = index

    records = []
    for row in reader:
        order_id = get_value(row, indices, "order_id").strip().upper()
        if not order_id:
            continue

        amount_value = get_value(row, indices, "amount")
        amount = parse_amount(amount_value)
        if amount is None:
            continue

        date_value = get_value(row, indices, "order_date")
        order_date = parse_date(date_value)
        if order_date is None:
            continue

        email = normalise_email(get_value(row, indices, "customer_email"))

        currency = get_value(row, indices, "currency").strip().upper()
        if currency:
            currency = CURRENCY_SYMBOLS.get(currency, currency)
        else:
            currency = symbol_in(amount_value) or "USD"

        status = normalise_status(get_value(row, indices, "status"))

        updated_at = parse_updated_at(get_value(row, indices, "updated_at"))

        records.append(
            {
                "order_id": order_id,
                "customer_email": email,
                "amount": format(amount, ".2f"),
                "currency": currency,
                "order_date": order_date.isoformat(),
                "status": status,
                "updated_at": updated_at,
            }
        )

    return records


def deduplicate(records):
    best = {}
    for record in records:
        order_id = record["order_id"]
        current = best.get(order_id)
        if current is None or record["updated_at"] >= current["updated_at"]:
            best[order_id] = record
    return list(best.values())


def write_output(path, records):
    records.sort(key=lambda record: (record["order_date"], record["order_id"]))
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(OUTPUT_FIELDS)
        for record in records:
            writer.writerow([record[field] for field in OUTPUT_FIELDS])


def main(argv):
    if len(argv) != 3:
        print("Usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2

    records = deduplicate(read_records(argv[1]))
    write_output(argv[2], records)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
