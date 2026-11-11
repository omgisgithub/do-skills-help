"""Clean and deduplicate order exports using only the standard library."""

import argparse
import csv
import re
from collections.abc import Iterator, Mapping
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from itertools import chain
from pathlib import Path
from typing import Optional, TextIO


FIELDS = ("order_id", "customer_email", "amount", "currency", "order_date", "status")
SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
MONTHS = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)
OLDEST = datetime.min.replace(tzinfo=timezone.utc)


def _records(source: TextIO) -> Iterator[list[str]]:
    lines = iter(source)
    for line in lines:
        if line.startswith("#") or not line.strip():
            continue
        # Let csv consume continuation lines so quoted newlines remain intact.
        yield next(csv.reader(chain((line,), lines), skipinitialspace=True))


def _amount(value: str) -> Optional[str]:
    text = "".join(char for char in value if not char.isspace() and char not in SYMBOLS)
    is_negative = text.startswith("(") and text.endswith(")")
    if is_negative:
        text = text[1:-1]
        if text.startswith(("+", "-")):
            return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        whole, fraction = text.rsplit(",", 1)
        if re.fullmatch(r"[0-9]{2}", fraction):
            text = whole.replace(",", "") + "." + fraction
        else:
            text = text.replace(",", "")
    if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", text):
        return None
    try:
        with localcontext() as context:
            context.prec = max(28, len(text) + 3)
            number = Decimal(text)
            if is_negative:
                number = -number
            return format(number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")
    except InvalidOperation:
        return None


def _order_date(value: str) -> Optional[str]:
    parts: Optional[tuple[int, int, int]] = None
    match = re.fullmatch(r"([0-9]{4})([-/])([0-9]{1,2})\2([0-9]{1,2})", value)
    if match:
        parts = (int(match[1]), int(match[3]), int(match[4]))
    match = re.fullmatch(r"([0-9]{1,2})([./])([0-9]{1,2})\2([0-9]{4})", value)
    if match:
        first, second, year = int(match[1]), int(match[3]), int(match[4])
        parts = (year, second, first) if match[2] == "." else (year, first, second)
    month_first = re.fullmatch(r"([A-Za-z]+)\s+([0-9]{1,2}),\s+([0-9]{4})", value)
    day_first = re.fullmatch(r"([0-9]{1,2})\s+([A-Za-z]+)\s+([0-9]{4})", value)
    if month_first:
        month_name, day, year = month_first.groups()
    elif day_first:
        day, month_name, year = day_first.groups()
    if month_first or day_first:
        for month, name in enumerate(MONTHS, 1):
            if month_name.lower() in (name, name[:3]):
                parts = (int(year), month, int(day))
                break
    if parts is None:
        return None
    try:
        return date(*parts).isoformat()
    except ValueError:
        return None


def _updated_at(value: str) -> datetime:
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}Z?", value):
        return OLDEST
    try:
        return datetime.fromisoformat(value.rstrip("Z")).replace(tzinfo=timezone.utc)
    except ValueError:
        return OLDEST


def _clean_row(row: Mapping[str, str]) -> Optional[dict[str, str]]:
    order_id = row.get("order_id", "").upper()
    amount = _amount(row.get("amount", ""))
    order_date = _order_date(row.get("order_date", ""))
    if not order_id or amount is None or order_date is None:
        return None
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
    return dict(zip(FIELDS, (
        order_id, email, amount, currency, order_date,
        status if status in STATUSES else "unknown",
    )))


def clean(input_path: Path, output_path: Path) -> None:
    """Write valid, normalized orders, keeping the latest valid row for each ID.

    Args:
        input_path: UTF-8 CSV export, optionally beginning with a BOM.
        output_path: Destination CSV with LF line endings.
    """
    orders: dict[str, tuple[datetime, dict[str, str]]] = {}
    with input_path.open(encoding="utf-8-sig", newline="") as source:
        records = _records(source)
        headers = [name.strip().lower().replace(" ", "_") for name in next(records, [])]
        for values in records:
            row = {name: value.strip() for name, value in zip(headers, values)}
            cleaned = _clean_row(row)
            if cleaned is None:
                continue
            updated_at = _updated_at(row.get("updated_at", ""))
            previous = orders.get(cleaned["order_id"])
            if previous is None or updated_at >= previous[0]:
                orders[cleaned["order_id"]] = (updated_at, cleaned)
    with output_path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(
            (row for _, row in orders.values()),
            key=lambda row: (row["order_date"], row["order_id"]),
        ))


def main() -> None:
    """Parse command-line paths and clean the requested export."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    clean(arguments.input, arguments.output)


if __name__ == "__main__":
    main()
