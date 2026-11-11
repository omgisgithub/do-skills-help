"""Clean a messy orders CSV export.

Usage:
    python3 clean.py INPUT.csv OUTPUT.csv
"""

from __future__ import annotations

import csv
import re
import sys
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

OUTPUT_COLUMNS = ("order_id", "customer_email", "amount", "currency", "order_date", "status")
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
CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
DEFAULT_CURRENCY = "USD"
DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d.%m.%Y",
    "%m/%d/%Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%d %b %Y",
    "%d %B %Y",
)
UPDATED_AT_FORMATS = ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S")
# Missing or unparseable updated_at values sort before every real timestamp.
OLDEST_UPDATED_AT = datetime.min
CENT = Decimal("0.01")

_AMOUNT_NOISE = re.compile(r"[\s$€£]")
_PLAIN_NUMBER = re.compile(r"[0-9]*\.?[0-9]+")


@dataclass(frozen=True)
class Order:
    """A cleaned order row, ready for output and de-duplication."""

    order_id: str
    customer_email: str
    amount: Decimal
    currency: str
    order_date: date
    status: str
    updated_at: datetime


def normalise_header(name: str) -> str:
    """Normalise a CSV header name to its snake_case form.

    Args:
        name: The raw header cell.

    Returns:
        The trimmed, lowercased name with spaces replaced by underscores.
    """
    return name.strip().lower().replace(" ", "_")


def parse_amount(raw: str) -> Decimal | None:
    """Parse a money amount into a Decimal rounded to cents.

    Accepts currency symbols, spaces, thousands separators and accounting
    negatives in parentheses. Rounds half away from zero.

    Args:
        raw: The raw amount cell.

    Returns:
        The amount with two decimals, or None if it cannot be parsed.
    """
    text = raw.strip()
    is_negative = text.startswith("(") and text.endswith(")")
    if is_negative:
        text = text[1:-1]
    text = _AMOUNT_NOISE.sub("", text)
    if text.startswith("-"):
        is_negative = True
        text = text[1:]
    text = _normalise_separators(text)
    if not _PLAIN_NUMBER.fullmatch(text):
        return None
    value = Decimal(text)
    if is_negative:
        value = -value
    rounded = value.quantize(CENT, rounding=ROUND_HALF_UP)
    # Avoid printing "-0.00" for amounts that round to zero.
    return abs(rounded) if rounded.is_zero() else rounded


def _normalise_separators(text: str) -> str:
    """Remove thousands separators and make the decimal separator a dot.

    Args:
        text: An amount with no whitespace or currency symbols.

    Returns:
        The text with ``.`` as the only possible decimal separator.
    """
    last_dot = text.rfind(".")
    last_comma = text.rfind(",")
    if last_dot != -1 and last_comma != -1:
        is_comma_decimal = last_comma > last_dot
    elif last_comma != -1:
        tail = text[last_comma + 1 :]
        is_comma_decimal = len(tail) == 2 and tail.isdigit()
    else:
        return text
    if is_comma_decimal:
        return text.replace(".", "").replace(",", ".")
    return text.replace(",", "")


def _symbol_currency(raw_amount: str) -> str | None:
    """Return the currency code for the first currency symbol in an amount.

    Args:
        raw_amount: The raw amount cell.

    Returns:
        The ISO code for the first known symbol, or None if there is none.
    """
    return next((CURRENCY_SYMBOLS[char] for char in raw_amount if char in CURRENCY_SYMBOLS), None)


def normalise_currency(raw_currency: str, raw_amount: str) -> str:
    """Normalise the currency, falling back to the amount's symbol.

    Args:
        raw_currency: The raw currency cell.
        raw_amount: The raw amount cell, consulted when the currency is empty.

    Returns:
        An uppercase currency code, ``USD`` if nothing indicates otherwise.
    """
    text = raw_currency.strip()
    if not text:
        return _symbol_currency(raw_amount) or DEFAULT_CURRENCY
    return CURRENCY_SYMBOLS.get(text, text.upper())


def parse_order_date(raw: str) -> date | None:
    """Parse an order date from one of the accepted input formats.

    Args:
        raw: The raw date cell.

    Returns:
        The parsed date, or None if the value is missing or invalid.
    """
    text = raw.strip()
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    return None


def parse_updated_at(raw: str) -> datetime:
    """Parse the updated_at timestamp used to pick the latest duplicate.

    The optional trailing ``Z`` is ignored: all timestamps are compared as
    the wall-clock values written in the file.

    Args:
        raw: The raw updated_at cell.

    Returns:
        The parsed timestamp, or ``OLDEST_UPDATED_AT`` if it is empty or invalid.
    """
    text = raw.strip().removesuffix("Z")
    for timestamp_format in UPDATED_AT_FORMATS:
        try:
            return datetime.strptime(text, timestamp_format)
        except ValueError:
            continue
    return OLDEST_UPDATED_AT


def normalise_email(raw: str) -> str:
    """Lowercase an email address, or blank it if it is not usable.

    Args:
        raw: The raw email cell.

    Returns:
        The lowercased address, or ``""`` if it does not contain exactly one
        ``@`` with text on both sides.
    """
    text = raw.strip().lower()
    local, _, domain = text.partition("@")
    is_valid = text.count("@") == 1 and bool(local.strip()) and bool(domain.strip())
    return text if is_valid else ""


def normalise_status(raw: str) -> str:
    """Map a raw status onto the allowed set, or ``unknown``.

    Args:
        raw: The raw status cell.

    Returns:
        The lowercased status, with ``canceled`` mapped to ``cancelled``.
    """
    text = raw.strip().lower()
    if text == "canceled":
        text = "cancelled"
    return text if text in ALLOWED_STATUSES else "unknown"


def build_order(fields: Mapping[str, str]) -> Order | None:
    """Clean one raw row into an Order, dropping rows that cannot be used.

    Args:
        fields: The required columns of the row, keyed by normalised header name.

    Returns:
        The cleaned order, or None if the order_id, amount or date is unusable.
    """
    order_id = fields["order_id"].strip().upper()
    amount = parse_amount(fields["amount"])
    order_date = parse_order_date(fields["order_date"])
    if not order_id or amount is None or order_date is None:
        return None
    return Order(
        order_id=order_id,
        customer_email=normalise_email(fields["customer_email"]),
        amount=amount,
        currency=normalise_currency(fields["currency"], fields["amount"]),
        order_date=order_date,
        status=normalise_status(fields["status"]),
        updated_at=parse_updated_at(fields["updated_at"]),
    )


def _content_lines(lines: Iterable[str]) -> Iterator[str]:
    """Yield only the lines that carry CSV content.

    Args:
        lines: The raw lines of the file.

    Yields:
        Every line except blank lines and lines starting with ``#``.
    """
    for line in lines:
        if line.strip() and not line.startswith("#"):
            yield line


def _column_positions(header: Sequence[str]) -> dict[str, int]:
    """Map each required column to its position in the header.

    Args:
        header: The raw header cells.

    Returns:
        The position of each required column, keyed by its normalised name.

    Raises:
        ValueError: If a required column is missing.
    """
    positions: dict[str, int] = {}
    for position, name in enumerate(header):
        positions.setdefault(normalise_header(name), position)
    missing = [column for column in REQUIRED_COLUMNS if column not in positions]
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")
    return {column: positions[column] for column in REQUIRED_COLUMNS}


def read_orders(path: Path) -> list[Order]:
    """Read and clean every usable order in a CSV export.

    Args:
        path: The path to the raw CSV file. A UTF-8 BOM is accepted.

    Returns:
        The cleaned orders, in file order, with unusable rows removed.

    Raises:
        ValueError: If the header lacks a required column.
    """
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(_content_lines(handle))
        header = next(reader, None)
        if header is None:
            return []
        positions = _column_positions(header)
        orders = [
            order
            for cells in reader
            if (order := build_order(_named_cells(positions, cells))) is not None
        ]
    return orders


def _named_cells(positions: Mapping[str, int], cells: Sequence[str]) -> dict[str, str]:
    """Pick the required columns out of one row, treating short rows as blank.

    Args:
        positions: The position of each required column.
        cells: The raw cells of the row.

    Returns:
        The cell value for each required column.
    """
    return {
        column: cells[position].strip() if position < len(cells) else ""
        for column, position in positions.items()
    }


def keep_latest_per_order(orders: Iterable[Order]) -> list[Order]:
    """Keep one order per order_id: the latest updated_at, ties going to the later row.

    Args:
        orders: The cleaned orders, in file order.

    Returns:
        The surviving orders, in no particular order.
    """
    latest: dict[str, Order] = {}
    for order in orders:
        current = latest.get(order.order_id)
        if current is None or order.updated_at >= current.updated_at:
            latest[order.order_id] = order
    return list(latest.values())


def write_orders(path: Path, orders: Sequence[Order]) -> None:
    """Write orders as a CSV with the output header.

    Args:
        path: The destination file. It is overwritten.
        orders: The orders to write, already sorted.
    """
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(OUTPUT_COLUMNS)
        for order in orders:
            writer.writerow(
                [
                    order.order_id,
                    order.customer_email,
                    f"{order.amount:.2f}",
                    order.currency,
                    order.order_date.isoformat(),
                    order.status,
                ]
            )


def main(argv: Sequence[str]) -> int:
    """Run the cleaner from the command line.

    Args:
        argv: The command line, including the program name.

    Returns:
        The process exit status.
    """
    if len(argv) != 3:
        sys.exit("usage: python3 clean.py INPUT.csv OUTPUT.csv")
    try:
        orders = read_orders(Path(argv[1]))
    except ValueError as exc:
        sys.exit(f"error: {exc}")
    kept = sorted(keep_latest_per_order(orders), key=lambda o: (o.order_date, o.order_id))
    write_orders(Path(argv[2]), kept)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
