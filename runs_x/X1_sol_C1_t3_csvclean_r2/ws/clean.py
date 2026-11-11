"""Normalize order exports using only the Python standard library."""

import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import re
import sys


FIELDS = ("order_id", "customer_email", "amount", "currency", "order_date", "status")
SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
MONTHS = {}
for number, name in enumerate(
    ("january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"), 1
):
    MONTHS[name] = MONTHS[name[:3]] = number


def parse_amount(value):
    """Return a two-decimal amount, or raise ValueError for invalid input."""
    value = "".join(char for char in value if not char.isspace() and char not in SYMBOLS)
    accounting = value.startswith("(") and value.endswith(")")
    if accounting:
        value = value[1:-1]
        if value.startswith(("+", "-")):
            raise ValueError("Signed accounting amount")
    if "." in value and "," in value:
        decimal_separator = "." if value.rfind(".") > value.rfind(",") else ","
        thousands_separator = "," if decimal_separator == "." else "."
        value = value.replace(thousands_separator, "").replace(decimal_separator, ".")
    elif "," in value:
        head, tail = value.rsplit(",", 1)
        if re.fullmatch(r"[0-9]{2}", tail):
            value = head.replace(",", "") + "." + tail
        else:
            value = value.replace(",", "")
    if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", value):
        raise ValueError("Invalid amount")
    try:
        with localcontext() as context:
            context.prec = max(28, len(value) + 4)
            amount = Decimal(value)
            if accounting:
                amount = -amount
            return format(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")
    except InvalidOperation as error:
        raise ValueError("Invalid amount") from error


def parse_date(value):
    """Accept only the explicitly supported numeric and English date forms."""
    match = re.fullmatch(r"([0-9]{4})([-/])([0-9]{1,2})\2([0-9]{1,2})", value)
    if match:
        year, _, month, day = match.groups()
    else:
        match = re.fullmatch(r"([0-9]{1,2})\.([0-9]{1,2})\.([0-9]{4})", value)
        if match:
            day, month, year = match.groups()
        else:
            match = re.fullmatch(r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})", value)
            if match:
                month, day, year = match.groups()
            else:
                match = re.fullmatch(r"([A-Za-z]+) ([0-9]{1,2}), ([0-9]{4})", value)
                if match:
                    month, day, year = match.groups()
                else:
                    match = re.fullmatch(r"([0-9]{1,2}) ([A-Za-z]+) ([0-9]{4})", value)
                    if not match:
                        raise ValueError("Invalid date form")
                    day, month, year = match.groups()
                month = MONTHS.get(month.lower())
                if month is None:
                    raise ValueError("Invalid month")
    return date(int(year), int(month), int(day)).isoformat()


def parse_updated_at(value):
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}Z?", value):
        try:
            return datetime.strptime(value.rstrip("Z").replace("T", " "), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    # Malformed timestamps, like missing timestamps, cannot establish recency.
    return datetime.min


def clean(input_path, output_path):
    orders = {}
    with open(input_path, encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(line for line in source if line.strip() and not line.startswith("#"))
        header = next(reader, [])
        names = [name.strip().lower().replace(" ", "_") for name in header]
        for values in reader:
            row = dict(zip(names, (value.strip() for value in values)))
            order_id = row.get("order_id", "").upper()
            if not order_id:
                continue
            try:
                amount = parse_amount(row.get("amount", ""))
                order_date = parse_date(row.get("order_date", ""))
            except ValueError:
                continue
            email = row.get("customer_email", "").lower()
            if email.count("@") != 1 or not all(email.split("@")):
                email = ""
            currency = row.get("currency", "").upper()
            if not currency:
                currency = next((SYMBOLS[char] for char in row.get("amount", "") if char in SYMBOLS), "USD")
            currency = SYMBOLS.get(currency, currency)
            status = row.get("status", "").lower()
            if status == "canceled":
                status = "cancelled"
            if status not in STATUSES:
                status = "unknown"
            updated_at = parse_updated_at(row.get("updated_at", ""))
            result = (order_id, email, amount, currency, order_date, status)
            if order_id not in orders or updated_at >= orders[order_id][0]:
                orders[order_id] = (updated_at, result)
    with open(output_path, "w", encoding="utf-8", newline="") as destination:
        writer = csv.writer(destination, lineterminator="\n")
        writer.writerow(FIELDS)
        writer.writerows(sorted((entry[1] for entry in orders.values()), key=lambda row: (row[4], row[0])))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python3 clean.py INPUT.csv OUTPUT.csv")
    clean(sys.argv[1], sys.argv[2])
