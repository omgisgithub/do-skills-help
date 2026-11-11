#!/usr/bin/env python3
"""Clean a messy order export.

Usage: python3 clean.py INPUT.csv OUTPUT.csv
"""

import csv
import datetime
import io
import re
import sys
from decimal import ROUND_HALF_UP, Decimal

OUTPUT_HEADER = ["order_id", "customer_email", "amount", "currency", "order_date", "status"]
SYMBOL_CURRENCY = {"$": "USD", "€": "EUR", "£": "GBP"}
ALLOWED_STATUS = {"pending", "paid", "shipped", "cancelled", "refunded"}
MONTHS = {}
for _number, _name in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1
):
    MONTHS[_name] = _number
    MONTHS[_name[:3]] = _number


def clean_email(raw):
    value = raw.strip().lower()
    if value.count("@") == 1 and all(part.strip() for part in value.split("@")):
        return value
    return ""


def clean_amount(raw):
    """Return (amount string with 2 decimals, currency from symbol or None), or None if invalid."""
    text = raw.strip()
    symbol_currency = None
    for char in text:
        if char in SYMBOL_CURRENCY:
            symbol_currency = SYMBOL_CURRENCY[char]
            break
    text = re.sub(r"[$€£\s]", "", text)

    negative = False
    if "(" in text or ")" in text:
        match = re.fullmatch(r"\((.*)\)", text)
        if not match:
            return None
        negative = True
        text = match.group(1)
    elif text.startswith("-"):
        negative = True
        text = text[1:]

    has_dot = "." in text
    has_comma = "," in text
    if has_dot and has_comma:
        decimal = "." if text.rfind(".") > text.rfind(",") else ","
        if text.count(decimal) > 1:
            return None
    elif has_dot:
        decimal = "." if text.count(".") == 1 else None
        if decimal is None:
            return None
    elif has_comma:
        decimal = "," if len(text) - text.rfind(",") - 1 == 2 else None
    else:
        decimal = None

    if decimal:
        index = text.rfind(decimal)
        int_part, frac = text[:index], text[index + 1:]
    else:
        int_part, frac = text, ""
    int_digits = int_part.replace(",", "").replace(".", "")
    if not re.fullmatch(r"\d*", int_digits) or not re.fullmatch(r"\d*", frac):
        return None
    if not int_digits and not frac:
        return None

    value = Decimal(f"{int_digits or '0'}.{frac or '0'}")
    if negative:
        value = -value
    value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if value == 0:
        value = abs(value)
    return f"{value:.2f}", symbol_currency


def clean_date(raw):
    text = raw.strip()
    match = re.fullmatch(r"(\d{4})([-/])(\d{1,2})\2(\d{1,2})", text)
    if match:
        year, month, day = match.group(1), match.group(3), match.group(4)
    else:
        match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
        if match:
            day, month, year = match.groups()
        else:
            match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
            if match:
                month, day, year = match.groups()
            else:
                match = re.fullmatch(r"([A-Za-z]+) (\d{1,2}), (\d{4})", text)
                if match and match.group(1).lower() in MONTHS:
                    month = MONTHS[match.group(1).lower()]
                    day, year = match.group(2), match.group(3)
                else:
                    match = re.fullmatch(r"(\d{1,2}) ([A-Za-z]+) (\d{4})", text)
                    if match and match.group(2).lower() in MONTHS:
                        day = match.group(1)
                        month = MONTHS[match.group(2).lower()]
                        year = match.group(3)
                    else:
                        return None
    try:
        return datetime.date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def clean_status(raw):
    value = raw.strip().lower()
    if value == "canceled":
        value = "cancelled"
    return value if value in ALLOWED_STATUS else "unknown"


def parse_updated(raw):
    """Return a datetime, or the oldest possible value if empty or invalid."""
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})Z?", raw.strip())
    if match:
        try:
            return datetime.datetime(*(int(part) for part in match.groups()))
        except ValueError:
            pass
    return datetime.datetime.min


def clean_row(get):
    """Clean one record. `get(name)` returns the trimmed raw value of a column."""
    order_id = get("order_id").upper()
    if not order_id:
        return None

    amount = clean_amount(get("amount"))
    if amount is None:
        return None
    amount_text, symbol_currency = amount

    order_date = clean_date(get("order_date"))
    if order_date is None:
        return None

    currency = get("currency").upper()
    currency = SYMBOL_CURRENCY.get(currency, currency)
    if not currency:
        currency = symbol_currency or "USD"

    return {
        "order_id": order_id,
        "customer_email": clean_email(get("customer_email")),
        "amount": amount_text,
        "currency": currency,
        "order_date": order_date,
        "status": clean_status(get("status")),
        "updated_at": parse_updated(get("updated_at")),
    }


def clean_file(input_path, output_path):
    with open(input_path, "rb") as handle:
        text = handle.read().decode("utf-8-sig")

    lines = [
        line for line in io.StringIO(text, newline="")
        if line.strip() and not line.startswith("#")
    ]
    reader = csv.reader(lines)
    header = next(reader, [])
    columns = {}
    for index, name in enumerate(header):
        key = re.sub(r"\s", "_", name.strip().lower())
        columns.setdefault(key, index)

    latest = {}
    for record in reader:
        def get(name, record=record):
            index = columns.get(name)
            if index is None or index >= len(record):
                return ""
            return record[index].strip()

        row = clean_row(get)
        if row is None:
            continue
        # Later rows win ties because the file is read in order.
        kept = latest.get(row["order_id"])
        if kept is None or row["updated_at"] >= kept["updated_at"]:
            latest[row["order_id"]] = row

    rows = sorted(latest.values(), key=lambda r: (r["order_date"], r["order_id"]))
    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(OUTPUT_HEADER)
        for row in rows:
            writer.writerow([row[column] for column in OUTPUT_HEADER])


def main(argv):
    if len(argv) != 3:
        print("usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2
    clean_file(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
