"""Clean order exports using only the Python 3.9 standard library."""

import argparse
import csv
import re
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Optional


OUTPUT_FIELDS = (
    "order_id", "customer_email", "amount", "currency", "order_date", "status"
)
CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = frozenset({"pending", "paid", "shipped", "cancelled", "refunded"})
MONTHS = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)
OLDEST = datetime.min.replace(tzinfo=timezone.utc)


def _parse_amount(value: str) -> Optional[str]:
    value = "".join(char for char in value if not char.isspace() and char not in CURRENCY_SYMBOLS)
    is_negative = value.startswith("(") and value.endswith(")")
    if is_negative:
        value = value[1:-1]
        if value.startswith(("+", "-")):
            return None
    if "." in value and "," in value:
        decimal_separator = "." if value.rfind(".") > value.rfind(",") else ","
        thousands_separator = "," if decimal_separator == "." else "."
        value = value.replace(thousands_separator, "").replace(decimal_separator, ".")
    elif "," in value:
        whole, fraction = value.rsplit(",", 1)
        if len(fraction) == 2 and fraction.isascii() and fraction.isdigit():
            value = whole.replace(",", "") + "." + fraction
        else:
            value = value.replace(",", "")
    if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", value):
        return None
    try:
        with localcontext() as context:
            context.prec = max(28, len(value) + 4)
            amount = Decimal(value)
            if is_negative:
                amount = -amount
            return format(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")
    except InvalidOperation:
        return None


def _parse_date(value: str) -> Optional[str]:
    year_first = re.fullmatch(r"([0-9]{4})([-/])([0-9]{1,2})\2([0-9]{1,2})", value)
    day_first = re.fullmatch(r"([0-9]{1,2})\.([0-9]{1,2})\.([0-9]{4})", value)
    month_first = re.fullmatch(r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})", value)
    named_month_first = re.fullmatch(r"([a-z]+)\s+([0-9]{1,2}),\s*([0-9]{4})", value.lower())
    named_day_first = re.fullmatch(r"([0-9]{1,2})\s+([a-z]+)\s+([0-9]{4})", value.lower())
    if year_first:
        year, _, month, day = year_first.groups()
    elif day_first:
        day, month, year = day_first.groups()
    elif month_first:
        month, day, year = month_first.groups()
    elif named_month_first or named_day_first:
        if named_month_first:
            month_name, day, year = named_month_first.groups()
        else:
            # The preceding condition guarantees one of the two matches exists.
            if named_day_first is None:
                return None
            day, month_name, year = named_day_first.groups()
        month_number = next(
            (number for number, name in enumerate(MONTHS, 1)
             if month_name in (name, name[:3])),
            None,
        )
        if month_number is None:
            return None
        month = str(month_number)
    else:
        return None
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def _parse_updated_at(value: str) -> datetime:
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}Z?", value):
        return OLDEST
    try:
        return datetime.strptime(value.rstrip("Z").replace("T", " "), "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return OLDEST


def _normalize_row(row: dict[str, str]) -> Optional[dict[str, str]]:
    order_id = row.get("order_id", "").upper()
    amount = _parse_amount(row.get("amount", ""))
    order_date = _parse_date(row.get("order_date", ""))
    if not order_id or amount is None or order_date is None:
        return None
    email = row.get("customer_email", "").lower()
    if email.count("@") != 1 or not all(email.split("@")):
        email = ""
    currency = row.get("currency", "").upper()
    if not currency:
        currency = next(
            (CURRENCY_SYMBOLS[char] for char in row.get("amount", "") if char in CURRENCY_SYMBOLS),
            "USD",
        )
    currency = CURRENCY_SYMBOLS.get(currency, currency)
    status = row.get("status", "").lower()
    if status == "canceled":
        status = "cancelled"
    return dict(zip(OUTPUT_FIELDS, (
        order_id, email, amount, currency, order_date, status if status in STATUSES else "unknown"
    )))


def clean_orders(input_path: Path, output_path: Path) -> None:
    """Normalize, deduplicate, and sort an order export.

    Args:
        input_path: UTF-8 CSV export to read.
        output_path: Destination for the cleaned UTF-8 CSV.
    """
    orders: dict[str, tuple[datetime, dict[str, str]]] = {}
    with input_path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(line for line in source if line.strip() and not line.startswith("#"))
        header = next(reader, [])
        fields = [field.strip().lower().replace(" ", "_") for field in header]
        for values in reader:
            row = {field: value.strip() for field, value in zip(fields, values)}
            cleaned = _normalize_row(row)
            if cleaned is None:
                continue
            updated_at = _parse_updated_at(row.get("updated_at", ""))
            order_id = cleaned["order_id"]
            if order_id not in orders or updated_at >= orders[order_id][0]:
                orders[order_id] = updated_at, cleaned
    sorted_orders = sorted(
        (row for _, row in orders.values()), key=lambda row: (row["order_date"], row["order_id"])
    )
    with output_path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted_orders)


def main() -> None:
    """Run the order export cleaner from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    clean_orders(arguments.input, arguments.output)


if __name__ == "__main__":
    main()
