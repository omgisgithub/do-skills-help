#!/usr/bin/env python3
"""Clean and normalize an exported orders CSV file."""

import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Optional, TextIO, Tuple


OUTPUT_FIELDS = (
    "order_id",
    "customer_email",
    "amount",
    "currency",
    "order_date",
    "status",
)
EXPECTED_FIELDS = OUTPUT_FIELDS + ("updated_at",)
SYMBOL_CURRENCIES = {"$": "USD", "€": "EUR", "£": "GBP"}
ALLOWED_STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
MONTHS = {
    name.lower(): number
    for number, names in enumerate(
        (
            (),
            ("January", "Jan"),
            ("February", "Feb"),
            ("March", "Mar"),
            ("April", "Apr"),
            ("May",),
            ("June", "Jun"),
            ("July", "Jul"),
            ("August", "Aug"),
            ("September", "Sep"),
            ("October", "Oct"),
            ("November", "Nov"),
            ("December", "Dec"),
        )
    )
    for name in names
}


def normalize_header(value: str) -> str:
    """Normalize a CSV header for matching."""
    return value.strip().lower().replace(" ", "_")


def parse_amount(value: str) -> Optional[Tuple[Decimal, Optional[str]]]:
    """Parse an amount and return its value and any currency symbol."""
    value = value.strip()
    symbol = next((item for item in SYMBOL_CURRENCIES if item in value), None)
    negative = value.startswith("(") and value.endswith(")")
    if negative:
        value = value[1:-1]
    value = re.sub(r"[$€£\s]", "", value)
    if value.count(".") and value.count(","):
        decimal_mark = "." if value.rfind(".") > value.rfind(",") else ","
        thousands_mark = "," if decimal_mark == "." else "."
        value = value.replace(thousands_mark, "").replace(decimal_mark, ".")
    elif "," in value:
        whole, tail = value.rsplit(",", 1)
        if len(tail) == 2 and tail.isdigit():
            value = whole.replace(",", "") + "." + tail
        else:
            value = value.replace(",", "")
    try:
        amount = Decimal(value)
    except InvalidOperation:
        return None
    if not amount.is_finite():
        return None
    if negative:
        amount = -amount
    return amount, symbol


def parse_order_date(value: str) -> Optional[date]:
    """Parse a supported order date format."""
    value = value.strip()
    formats = (
        (r"\d{4}-\d{1,2}-\d{1,2}", "%Y-%m-%d"),
        (r"\d{4}/\d{1,2}/\d{1,2}", "%Y/%m/%d"),
        (r"\d{1,2}\.\d{1,2}\.\d{4}", "%d.%m.%Y"),
        (r"\d{1,2}/\d{1,2}/\d{4}", "%m/%d/%Y"),
    )
    for pattern, fmt in formats:
        if re.fullmatch(pattern, value):
            parts = [int(part) for part in re.split(r"[-/.]", value)]
            try:
                if fmt == "%Y-%m-%d" or fmt == "%Y/%m/%d":
                    return date(parts[0], parts[1], parts[2])
                if fmt == "%d.%m.%Y":
                    return date(parts[2], parts[1], parts[0])
                return date(parts[2], parts[0], parts[1])
            except ValueError:
                return None
    month_pattern = r"([A-Za-z]+)"
    first = re.fullmatch(rf"{month_pattern}\s+(\d{{1,2}}),?\s+(\d{{4}})", value)
    second = re.fullmatch(rf"(\d{{1,2}})\s+{month_pattern}\s+(\d{{4}})", value)
    try:
        if first:
            month = MONTHS[first.group(1).lower()]
            return date(int(first.group(3)), month, int(first.group(2)))
        if second:
            month = MONTHS[second.group(2).lower()]
            return date(int(second.group(3)), month, int(second.group(1)))
    except (KeyError, ValueError):
        return None
    return None


def updated_key(value: str) -> tuple[int, ...]:
    """Return a sortable timestamp key, treating empty or invalid values as oldest."""
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1]
    value = value.replace("T", " ")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return (0,)
    return (parsed.year, parsed.month, parsed.day, parsed.hour, parsed.minute, parsed.second)


def clean_row(
    row: dict[str, Optional[str]], index: int
) -> Optional[Tuple[dict[str, str], Tuple[int, ...], int]]:
    """Normalize one row, dropping it when required fields are invalid."""
    values = {key: (row.get(key) or "").strip() for key in EXPECTED_FIELDS}
    order_id = values["order_id"].upper()
    if not order_id:
        return None
    parsed_amount = parse_amount(values["amount"])
    order_date = parse_order_date(values["order_date"])
    if parsed_amount is None or order_date is None:
        return None
    amount, symbol = parsed_amount
    email = values["customer_email"].lower()
    if email.count("@") != 1 or any(not part for part in email.split("@")):
        email = ""
    currency = values["currency"].upper()
    currency = SYMBOL_CURRENCIES.get(currency, currency)
    if not currency:
        currency = SYMBOL_CURRENCIES.get(symbol or "", "USD")
    status = values["status"].lower()
    if status == "canceled":
        status = "cancelled"
    if status not in ALLOWED_STATUSES:
        status = "unknown"
    output = {
        "order_id": order_id,
        "customer_email": email,
        "amount": str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        "currency": currency,
        "order_date": order_date.isoformat(),
        "status": status,
    }
    return output, updated_key(values["updated_at"]), index


def non_comment_lines(file: TextIO) -> list[str]:
    """Remove blank and comment lines while preserving CSV content."""
    return [line for line in file if line.strip() and not line.startswith("#")]


def clean_file(input_path: Path, output_path: Path) -> None:
    """Read, normalize, de-duplicate, sort, and write an order CSV."""
    with input_path.open("r", encoding="utf-8-sig", newline="") as source:
        lines = non_comment_lines(source)
    reader = csv.DictReader(lines)
    if reader.fieldnames is not None:
        reader.fieldnames = [normalize_header(name) for name in reader.fieldnames]
    latest: dict[str, Tuple[dict[str, str], Tuple[int, ...], int]] = {}
    for index, row in enumerate(reader):
        cleaned = clean_row(row, index)
        if cleaned is None:
            continue
        previous = latest.get(cleaned[0]["order_id"])
        if previous is None or cleaned[1:] >= previous[1:]:
            latest[cleaned[0]["order_id"]] = cleaned
    rows = sorted((item[0] for item in latest.values()), key=lambda item: (item["order_date"], item["order_id"]))
    with output_path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    """Run the command-line CSV cleaner."""
    if len(sys.argv) != 3:
        print("Usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2
    clean_file(Path(sys.argv[1]), Path(sys.argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
