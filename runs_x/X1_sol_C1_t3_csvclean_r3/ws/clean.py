"""Normalize order exports using only the Python standard library."""

import argparse
import csv
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext


FIELDS = ("order_id", "customer_email", "amount", "currency", "order_date", "status")
SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
MONTHS = {}
for number, name in enumerate(("January", "February", "March", "April", "May", "June",
                               "July", "August", "September", "October", "November",
                               "December"), 1):
    MONTHS[name.lower()] = number
    MONTHS[name[:3].lower()] = number


def parse_amount(value):
    text = "".join(char for char in value if not char.isspace() and char not in SYMBOLS)
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
        if text.startswith(("+", "-")):
            raise ValueError("Signed accounting amount")
    if "." in text and "," in text:
        decimal_sep = "." if text.rfind(".") > text.rfind(",") else ","
        text = text.replace("," if decimal_sep == "." else ".", "")
        text = text.replace(decimal_sep, ".")
    elif "," in text:
        before, after = text.rsplit(",", 1)
        if re.fullmatch(r"[0-9]{2}", after):
            text = before.replace(",", "") + "." + after
        else:
            text = text.replace(",", "")
    if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", text):
        raise ValueError("Invalid amount")
    with localcontext() as context:
        context.prec = max(28, len(text) + 3)
        amount = Decimal(text)
        if negative:
            amount = -amount
        return format(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")


def parse_date(value):
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
                        raise ValueError("Invalid date format")
                    day, month, year = match.groups()
                month = MONTHS.get(month.lower(), 0)
    return date(int(year), int(month), int(day)).isoformat()


def parse_updated(value):
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
        reader = csv.DictReader(line for line in source if line.strip() and not line.startswith("#"))
        if reader.fieldnames is not None:
            reader.fieldnames = [name.strip().lower().replace(" ", "_") for name in reader.fieldnames]
        for raw in reader:
            row = {key: (raw.get(key) or "").strip() for key in (*FIELDS, "updated_at")}
            row["order_id"] = row["order_id"].upper()
            if not row["order_id"]:
                continue
            original_amount = row["amount"]
            try:
                row["amount"] = parse_amount(original_amount)
                row["order_date"] = parse_date(row["order_date"])
            except (ValueError, InvalidOperation):
                continue
            email = row["customer_email"].lower()
            row["customer_email"] = email if email.count("@") == 1 and all(email.split("@")) else ""
            currency = row["currency"].upper()
            if not currency:
                currency = next((SYMBOLS[c] for c in original_amount if c in SYMBOLS), "USD")
            row["currency"] = SYMBOLS.get(currency, currency)
            status = row["status"].lower()
            if status == "canceled":
                status = "cancelled"
            row["status"] = status if status in {"pending", "paid", "shipped", "cancelled", "refunded"} else "unknown"
            updated = parse_updated(row.pop("updated_at"))
            previous = orders.get(row["order_id"])
            if previous is None or updated >= previous[0]:
                orders[row["order_id"]] = (updated, row)
    with open(output_path, "w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted((entry[1] for entry in orders.values()),
                               key=lambda row: (row["order_date"], row["order_id"])))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("output")
    args = parser.parse_args()
    clean(args.input, args.output)
