"""Clean a messy order export CSV into a normalised CSV.

Usage:
    python3 clean.py INPUT.csv OUTPUT.csv
"""

from __future__ import annotations

import csv
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import TextIO

OUTPUT_HEADER = ("order_id", "customer_email", "amount", "currency", "order_date", "status")
REQUIRED_COLUMNS = (
    "order_id",
    "customer_email",
    "amount",
    "currency",
    "order_date",
    "status",
    "updated_at",
)
ALLOWED_STATUSES = frozenset({"pending", "paid", "shipped", "cancelled", "refunded"})
STATUS_ALIASES = {"canceled": "cancelled"}
CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
DEFAULT_CURRENCY = "USD"
DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d.%m.%Y",
    "%m/%d/%Y",
    "%b %d, %Y",
    "%b %d %Y",
    "%B %d, %Y",
    "%B %d %Y",
    "%d %b %Y",
    "%d %B %Y",
)
UPDATED_AT_FORMAT = "%Y-%m-%d %H:%M:%S"
CENT = Decimal("0.01")

# Parenthesised amounts are accounting negatives; a leading "-" is a plain negative.
_AMOUNT_PATTERN = re.compile(r"\((?P<paren>[0-9.,]+)\)|(?P<sign>-?)(?P<plain>[0-9.,]+)")
_PLAIN_NUMBER_PATTERN = re.compile(r"[0-9]+(?:\.[0-9]*)?|\.[0-9]+")


@dataclass(frozen=True)
class OrderRow:
    """One normalised order line, before de-duplication.

    Attributes:
        order_id: Trimmed, uppercased identifier.
        customer_email: Lowercased email, or an empty string if invalid.
        amount: Amount with exactly two decimals.
        currency: Upper-case ISO-style currency code.
        order_date: Date in ``YYYY-MM-DD`` form.
        status: One of ``ALLOWED_STATUSES`` or ``unknown``.
        updated_at: Naive timestamp used for de-duplication; ``datetime.min`` if unknown.
    """

    order_id: str
    customer_email: str
    amount: str
    currency: str
    order_date: str
    status: str
    updated_at: datetime

    def as_output_fields(self) -> tuple[str, ...]:
        """Return the fields written to the output CSV, in header order."""
        return (
            self.order_id,
            self.customer_email,
            self.amount,
            self.currency,
            self.order_date,
            self.status,
        )


def clean_file(input_path: Path, output_path: Path) -> None:
    """Read a messy order export and write the cleaned CSV.

    Args:
        input_path: The raw export to read. May start with a UTF-8 BOM.
        output_path: Destination for the cleaned CSV. Overwritten if it exists.

    Raises:
        ValueError: If the input lacks a required column.
        OSError: If either file cannot be read or written.
    """
    with input_path.open(encoding="utf-8-sig", newline="") as source:
        records = read_records(source)
    orders = [order for order in map(clean_record, records) if order is not None]
    rows = sorted(keep_latest(orders), key=lambda order: (order.order_date, order.order_id))
    with output_path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target, lineterminator="\n")
        writer.writerow(OUTPUT_HEADER)
        writer.writerows(order.as_output_fields() for order in rows)


def read_records(source: TextIO) -> list[dict[str, str]]:
    """Parse the export into header-keyed records with trimmed values.

    Blank lines and lines starting with ``#`` are skipped before CSV parsing.

    Args:
        source: Text stream positioned at the start of the export.

    Returns:
        One mapping per data row, keyed by normalised header name.

    Raises:
        ValueError: If the header is missing a required column.
    """
    data_lines = (line for line in source if _is_data_line(line))
    reader = csv.reader(data_lines)
    header = next(reader, None)
    if header is None:
        return []
    names = [normalise_header(name) for name in header]
    missing = [column for column in REQUIRED_COLUMNS if column not in names]
    if missing:
        raise ValueError(f"input is missing required columns: {', '.join(missing)}")
    return [dict(zip(names, (value.strip() for value in values))) for values in reader if values]


def _is_data_line(line: str) -> bool:
    """Return whether a raw input line should be parsed as CSV."""
    return bool(line.strip()) and not line.startswith("#")


def normalise_header(name: str) -> str:
    """Normalise a header cell to a column key, e.g. ``" Order ID "`` to ``order_id``."""
    return name.strip().lower().replace(" ", "_")


def clean_record(record: Mapping[str, str]) -> OrderRow | None:
    """Normalise one raw record.

    Args:
        record: Header-keyed values with surrounding whitespace already trimmed.

    Returns:
        The normalised row, or ``None`` if the row must be dropped.
    """
    order_id = record.get("order_id", "").upper()
    amount = parse_amount(record.get("amount", ""))
    order_date = parse_date(record.get("order_date", ""))
    if not order_id or amount is None or order_date is None:
        return None
    return OrderRow(
        order_id=order_id,
        customer_email=normalise_email(record.get("customer_email", "")),
        amount=f"{amount:.2f}",
        currency=resolve_currency(record.get("currency", ""), record.get("amount", "")),
        order_date=order_date.isoformat(),
        status=normalise_status(record.get("status", "")),
        updated_at=parse_updated_at(record.get("updated_at", "")),
    )


def parse_amount(text: str) -> Decimal | None:
    """Parse a free-form money amount, rounded half away from zero to two decimals.

    Currency symbols and whitespace are ignored. Returns ``None`` when the text
    cannot be read as an amount.

    Args:
        text: Raw amount cell, e.g. ``"$1,234.50"`` or ``"(12.50)"``.

    Returns:
        The rounded amount, or ``None`` if the text is empty or unparseable.
    """
    compact = "".join(ch for ch in text if ch not in CURRENCY_SYMBOLS and not ch.isspace())
    match = _AMOUNT_PATTERN.fullmatch(compact)
    if match is None:
        return None
    if match.group("paren") is not None:
        digits, is_negative = match.group("paren"), True
    else:
        digits, is_negative = match.group("plain"), match.group("sign") == "-"
    value = _parse_digits(digits)
    if value is None:
        return None
    if is_negative:
        value = -value
    try:
        return value.quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def _parse_digits(digits: str) -> Decimal | None:
    """Convert digits with thousands and decimal separators to a Decimal."""
    separator = _decimal_separator(digits)
    if separator is None:
        plain = digits.replace(",", "")
    else:
        thousands = "," if separator == "." else "."
        head, _, tail = digits.rpartition(separator)
        plain = f"{head.replace(thousands, '')}.{tail}"
    if _PLAIN_NUMBER_PATTERN.fullmatch(plain) is None:
        return None
    return Decimal(plain)


def _decimal_separator(digits: str) -> str | None:
    """Return the decimal separator in a number, or ``None`` if it has none.

    When both separators appear, the last one is the decimal separator. A lone
    comma is decimal only when exactly two digits follow it.
    """
    if "." in digits and "," in digits:
        return "." if digits.rfind(".") > digits.rfind(",") else ","
    if "," in digits:
        tail = digits.rsplit(",", 1)[1]
        return "," if len(tail) == 2 and tail.isdigit() else None
    if "." in digits:
        return "."
    return None


def resolve_currency(currency: str, amount: str) -> str:
    """Pick the currency code from the currency cell, falling back to the amount's symbol.

    Args:
        currency: Trimmed currency cell; may be a code or a symbol.
        amount: Raw amount cell, searched for a currency symbol when ``currency`` is empty.

    Returns:
        An upper-case currency code, defaulting to ``USD``.
    """
    if currency:
        code = currency.upper()
        return CURRENCY_SYMBOLS.get(code, code)
    for symbol, code in CURRENCY_SYMBOLS.items():
        if symbol in amount:
            return code
    return DEFAULT_CURRENCY


def normalise_email(text: str) -> str:
    """Lowercase an email address, or return ``""`` if it is not usable.

    An address is usable when it contains exactly one ``@`` with text on both sides.
    """
    email = text.lower()
    local, _, domain = email.partition("@")
    if email.count("@") != 1 or not local or not domain:
        return ""
    return email


def parse_date(text: str) -> date | None:
    """Parse one of the accepted date spellings into a date.

    Args:
        text: Raw date cell, e.g. ``"03/04/2026"`` or ``"Mar 4, 2026"``.

    Returns:
        The parsed date, or ``None`` if no accepted format matches a valid date.
    """
    cleaned = " ".join(text.split())
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, date_format).date()
        except ValueError:
            continue
    return None


def normalise_status(text: str) -> str:
    """Map a raw status to one of the allowed statuses, or ``unknown``."""
    status = STATUS_ALIASES.get(text.lower(), text.lower())
    return status if status in ALLOWED_STATUSES else "unknown"


def parse_updated_at(text: str) -> datetime:
    """Parse an ``updated_at`` cell, treating empty or invalid values as the oldest possible.

    Args:
        text: Raw timestamp, e.g. ``"2026-03-04T10:00:00Z"`` or ``"2026-03-04 10:00:00"``.

    Returns:
        A naive timestamp for ordering; ``datetime.min`` if the value is empty or invalid.
    """
    if not text:
        return datetime.min
    normalised = text.removesuffix("Z").replace("T", " ", 1)
    try:
        return datetime.strptime(normalised, UPDATED_AT_FORMAT)
    except ValueError:
        return datetime.min


def keep_latest(orders: Sequence[OrderRow]) -> list[OrderRow]:
    """Keep one row per order ID: the latest ``updated_at``, ties going to the later row.

    Args:
        orders: Normalised rows in file order.

    Returns:
        One row per distinct ``order_id``, in no particular order.
    """
    latest: dict[str, OrderRow] = {}
    for order in orders:
        current = latest.get(order.order_id)
        if current is None or order.updated_at >= current.updated_at:
            latest[order.order_id] = order
    return list(latest.values())


def main(argv: Sequence[str]) -> int:
    """Run the cleaner from the command line.

    Args:
        argv: Two arguments: input path and output path.

    Returns:
        Process exit code: 0 on success, 1 on a processing error, 2 on bad usage.
    """
    if len(argv) != 2:
        sys.stderr.write("usage: python3 clean.py INPUT.csv OUTPUT.csv\n")
        return 2
    try:
        clean_file(Path(argv[0]), Path(argv[1]))
    except (OSError, ValueError, csv.Error) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
