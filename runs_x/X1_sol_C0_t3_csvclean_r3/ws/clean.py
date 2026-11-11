"""Clean an order export: python3 clean.py INPUT.csv OUTPUT.csv."""

import argparse
import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import re


FIELDS = ("order_id", "customer_email", "amount", "currency", "order_date", "status")
SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
MONTHS = {}
for number, name in enumerate(
    ("January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"), 1
):
    MONTHS[name.lower()] = number
    MONTHS[name[:3].lower()] = number


def parse_amount(value):
    """Return a fixed-point amount, or None for invalid input."""
    value = "".join(c for c in value if not c.isspace() and c not in SYMBOLS)
    negative = value.startswith("(") and value.endswith(")")
    if negative:
        value = value[1:-1]
        # Parentheses supply the sign; a second sign is not a valid amount.
        if value.startswith(("+", "-")):
            return None

    if "." in value and "," in value:
        decimal = "." if value.rfind(".") > value.rfind(",") else ","
        thousands = "," if decimal == "." else "."
        value = value.replace(thousands, "").replace(decimal, ".")
    elif "," in value:
        whole, fraction = value.rsplit(",", 1)
        if re.fullmatch(r"[0-9]{2}", fraction):
            value = whole.replace(",", "") + "." + fraction
        else:
            value = value.replace(",", "")

    if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", value):
        return None
    try:
        with localcontext() as context:
            context.prec = max(28, len(value) + 4)
            amount = Decimal(value)
            if negative:
                amount = -amount
            return format(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")
    except InvalidOperation:
        return None


def parse_date(value):
    """Parse only the specified numeric forms and English month names."""
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
                match = re.fullmatch(r"([A-Za-z]+)\s+([0-9]{1,2}),\s+([0-9]{4})", value)
                if match:
                    name, day, year = match.groups()
                else:
                    match = re.fullmatch(r"([0-9]{1,2})\s+([A-Za-z]+)\s+([0-9]{4})", value)
                    if not match:
                        return None
                    day, name, year = match.groups()
                month = MONTHS.get(name.lower())
                if month is None:
                    return None
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def parse_updated_at(value):
    if not value:
        return datetime.min
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}Z?", value):
        return datetime.min
    try:
        return datetime.strptime(value.rstrip("Z").replace("T", " "), "%Y-%m-%d %H:%M:%S")
    except ValueError:
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
                currency = next((SYMBOLS[c] for c in row["amount"] if c in SYMBOLS), "USD")
            currency = SYMBOLS.get(currency, currency)
            status = row["status"].lower()
            if status == "canceled":
                status = "cancelled"
            if status not in STATUSES:
                status = "unknown"
            updated = parse_updated_at(row["updated_at"])
            if order_id not in orders or updated >= orders[order_id][0]:
                orders[order_id] = (updated, (order_id, email, amount, currency, order_date, status))

    with open(output_path, "w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target, lineterminator="\n")
        writer.writerow(FIELDS)
        writer.writerows(sorted((entry[1] for entry in orders.values()), key=lambda row: (row[4], row[0])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv")
    parser.add_argument("output_csv")
    args = parser.parse_args()
    clean(args.input_csv, args.output_csv)


if __name__ == "__main__":
    main()
