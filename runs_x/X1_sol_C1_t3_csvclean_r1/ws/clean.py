"""Clean an order export: python3 clean.py INPUT.csv OUTPUT.csv."""

import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import re
import sys


FIELDS = ("order_id", "customer_email", "amount", "currency", "order_date", "status")
SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
MONTHS = {}
for number, month in enumerate(("January", "February", "March", "April", "May",
                                "June", "July", "August", "September", "October",
                                "November", "December"), 1):
    MONTHS[month.lower()] = MONTHS[month[:3].lower()] = number


def parse_amount(value):
    """Return a rounded amount, or None for an invalid amount."""
    value = "".join(char for char in value if not char.isspace() and char not in SYMBOLS)
    negative = value.startswith("(") and value.endswith(")")
    if negative:
        value = value[1:-1]
        if value.startswith(("+", "-")):
            return None
    if "." in value and "," in value:
        if value.rfind(".") > value.rfind(","):
            value = value.replace(",", "")
        else:
            value = value.replace(".", "").replace(",", ".")
    elif "," in value:
        head, tail = value.rsplit(",", 1)
        if re.fullmatch(r"[0-9]{2}", tail):
            value = head.replace(",", "") + "." + tail
        else:
            value = value.replace(",", "")
    if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", value):
        return None
    try:
        with localcontext() as context:
            context.prec = max(28, len(value) + 3)
            amount = Decimal(value)
            if negative:
                amount = -amount
            return format(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")
    except InvalidOperation:
        return None


def parse_date(value):
    """Accept only the numeric and English date forms in the export format."""
    match = re.fullmatch(r"([0-9]{4})([-/])([0-9]{1,2})\2([0-9]{1,2})", value)
    if match:
        year, month, day = int(match[1]), int(match[3]), int(match[4])
    else:
        match = re.fullmatch(r"([0-9]{1,2})([./])([0-9]{1,2})\2([0-9]{4})", value)
        if match:
            first, second, year = int(match[1]), int(match[3]), int(match[4])
            day, month = (first, second) if match[2] == "." else (second, first)
        else:
            match = re.fullmatch(r"([A-Za-z]+) ([0-9]{1,2}), ([0-9]{4})", value)
            if match:
                month, day, year = MONTHS.get(match[1].lower(), 0), int(match[2]), int(match[3])
            else:
                match = re.fullmatch(r"([0-9]{1,2}) ([A-Za-z]+) ([0-9]{4})", value)
                if not match:
                    return None
                day, month, year = int(match[1]), MONTHS.get(match[2].lower(), 0), int(match[3])
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def parse_updated_at(value):
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}Z?", value):
        try:
            return datetime.strptime(value.rstrip("Z").replace("T", " "), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return datetime.min


def clean(input_path, output_path):
    orders = {}
    with open(input_path, encoding="utf-8-sig", newline="") as source:
        lines = (line for line in source if line.strip() and not line.startswith("#"))
        reader = csv.DictReader(lines)
        if reader.fieldnames is not None:
            reader.fieldnames = [name.strip().lower().replace(" ", "_") for name in reader.fieldnames]
        for raw in reader:
            row = {key: (raw.get(key) or "").strip() for key in FIELDS + ("updated_at",)}
            order_id = row["order_id"].upper()
            amount = parse_amount(row["amount"])
            order_date = parse_date(row["order_date"])
            if not order_id or amount is None or order_date is None:
                continue
            email = row["customer_email"].lower()
            if email.count("@") != 1 or not all(email.split("@")):
                email = ""
            currency = row["currency"].upper()
            if not currency:
                currency = next((SYMBOLS[char] for char in row["amount"] if char in SYMBOLS), "USD")
            currency = SYMBOLS.get(currency, currency)
            status = row["status"].lower()
            if status == "canceled":
                status = "cancelled"
            if status not in STATUSES:
                status = "unknown"
            updated_at = parse_updated_at(row["updated_at"])
            if order_id not in orders or updated_at >= orders[order_id][0]:
                orders[order_id] = (updated_at, (order_id, email, amount, currency, order_date, status))
    with open(output_path, "w", encoding="utf-8", newline="") as destination:
        writer = csv.writer(destination, lineterminator="\n")
        writer.writerow(FIELDS)
        writer.writerows(sorted((entry[1] for entry in orders.values()), key=lambda row: (row[4], row[0])))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: python3 clean.py INPUT.csv OUTPUT.csv")
    clean(sys.argv[1], sys.argv[2])
