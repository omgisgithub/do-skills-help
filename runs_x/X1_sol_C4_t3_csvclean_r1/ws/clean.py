"""Clean an order export using only the Python 3.9 standard library."""

from __future__ import annotations

import argparse
import csv
import re
from collections.abc import Iterator, Mapping
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, localcontext
from itertools import chain
from pathlib import Path
from typing import Optional, TextIO

OUTPUT_FIELDS = ("order_id", "customer_email", "amount", "currency", "order_date", "status")
CURRENCIES = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
MONTHS = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)


def _csv_rows(source: TextIO) -> Iterator[list[str]]:
    # Start filtering at record boundaries so quoted multiline values remain intact.
    for line in source:
        if not line.strip() or line.startswith("#"):
            continue
        yield next(csv.reader(chain((line,), source)))


def _amount(raw: str) -> Optional[str]:
    value = "".join(char for char in raw if not char.isspace() and char not in CURRENCIES)
    is_negative = value.startswith("(") and value.endswith(")")
    if is_negative:
        value = value[1:-1]
        if value.startswith(("+", "-")):
            return None
    if "." in value and "," in value:
        if value.rfind(".") > value.rfind(","):
            value = value.replace(",", "")
        else:
            value = value.replace(".", "").replace(",", ".")
    elif "," in value:
        integer, fraction = value.rsplit(",", 1)
        if len(fraction) == 2 and fraction.isascii() and fraction.isdigit():
            value = integer.replace(",", "") + "." + fraction
        else:
            value = value.replace(",", "")
    if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", value):
        return None
    # Size precision to the input rather than the default 28 significant digits.
    with localcontext() as context:
        context.prec = len(value) + 3
        number = Decimal(value)
        if is_negative:
            number = -number
        return format(number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")


def _order_date(value: str) -> Optional[str]:
    parts: Optional[tuple[int, int, int]] = None
    match = re.fullmatch(r"([0-9]{4})([-/])([0-9]{1,2})\2([0-9]{1,2})", value)
    if match:
        parts = (int(match[1]), int(match[3]), int(match[4]))
    match = re.fullmatch(r"([0-9]{1,2})([./])([0-9]{1,2})\2([0-9]{4})", value)
    if match:
        first, second = int(match[1]), int(match[3])
        month, day = (second, first) if match[2] == "." else (first, second)
        parts = (int(match[4]), month, day)
    match = re.fullmatch(r"([A-Za-z]+)\s+([0-9]{1,2}),\s+([0-9]{4})", value)
    if match:
        parts = _named_date(match[1], match[2], match[3])
    match = re.fullmatch(r"([0-9]{1,2})\s+([A-Za-z]+)\s+([0-9]{4})", value)
    if match:
        parts = _named_date(match[2], match[1], match[3])
    if parts is None:
        return None
    try:
        return date(*parts).isoformat()
    except ValueError:
        return None  # Invalid calendar dates are explicitly dropped by the export rules.


def _named_date(month_name: str, day: str, year: str) -> Optional[tuple[int, int, int]]:
    for month, name in enumerate(MONTHS, 1):
        if month_name.lower() in (name, name[:3]):
            return int(year), month, int(day)
    return None


def _updated_at(value: str) -> datetime:
    oldest = datetime.min.replace(tzinfo=timezone.utc)
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}Z?", value):
        return oldest
    try:
        return datetime.fromisoformat(value.removesuffix("Z")).replace(tzinfo=timezone.utc)
    except ValueError:
        return oldest  # Unusable timestamps have the same priority as missing timestamps.


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
        currency = next((CURRENCIES[c] for c in row.get("amount", "") if c in CURRENCIES), "USD")
    currency = CURRENCIES.get(currency, currency)
    status = row.get("status", "").lower()
    if status == "canceled":
        status = "cancelled"
    return {
        "order_id": order_id,
        "customer_email": email,
        "amount": amount,
        "currency": currency,
        "order_date": order_date,
        "status": status if status in STATUSES else "unknown",
    }


def clean(input_path: Path, output_path: Path) -> None:
    """Validate, deduplicate, and sort an order CSV into a clean export.

    Args:
        input_path: UTF-8 CSV export, optionally starting with a BOM.
        output_path: Destination for the six-column UTF-8 CSV.
    """
    orders: dict[str, tuple[datetime, dict[str, str]]] = {}
    with input_path.open(encoding="utf-8-sig", newline="") as source:
        records = _csv_rows(source)
        header = [name.strip().lower().replace(" ", "_") for name in next(records, [])]
        for values in records:
            row = {name: value.strip() for name, value in zip(header, values)}
            cleaned = _clean_row(row)
            if cleaned is None:
                continue
            updated_at = _updated_at(row.get("updated_at", ""))
            order_id = cleaned["order_id"]
            if order_id not in orders or updated_at >= orders[order_id][0]:
                orders[order_id] = updated_at, cleaned
    rows = sorted((row for _, row in orders.values()), key=lambda r: (r["order_date"], r["order_id"]))
    with output_path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """Parse command-line paths and clean the requested order export."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    clean(args.input, args.output)


if __name__ == "__main__":
    main()
