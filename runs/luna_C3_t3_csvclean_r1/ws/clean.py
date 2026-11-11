import csv
import re
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


OUTPUT_FIELDS = (
    "order_id",
    "customer_email",
    "amount",
    "currency",
    "order_date",
    "status",
)
STATUS_VALUES = {"pending", "paid", "shipped", "cancelled", "refunded"}
CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}


def normalize_header(value):
    return value.strip().lower().replace(" ", "_")


def parse_amount(value):
    text = value.strip()
    if not text:
        raise ValueError("empty amount")

    symbol_currency = next(
        (currency for symbol, currency in CURRENCY_SYMBOLS.items() if symbol in text),
        "",
    )
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    for symbol in CURRENCY_SYMBOLS:
        text = text.replace(symbol, "")
    text = re.sub(r"\s+", "", text)

    if "." in text and "," in text:
        decimal_separator = "." if text.rfind(".") > text.rfind(",") else ","
        thousands_separator = "," if decimal_separator == "." else "."
        text = text.replace(thousands_separator, "")
        if decimal_separator == ",":
            text = text.replace(",", ".")
    elif "," in text:
        last_comma = text.rfind(",")
        if len(text) - last_comma - 1 == 2:
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")

    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", text):
        raise ValueError("invalid amount")
    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("invalid amount") from exc
    if negative:
        amount = -amount
    try:
        amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError("invalid amount") from exc
    return amount, symbol_currency


def parse_order_date(value):
    text = value.strip()
    formats = (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d.%m.%Y",
        "%m/%d/%Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%b %d %Y",
        "%B %d %Y",
        "%d %b %Y",
        "%d %B %Y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError("invalid date")


def parse_updated_at(value):
    text = value.strip()
    if not text:
        return datetime.min
    if text.endswith("Z"):
        text = text[:-1]
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return datetime.min


def clean_row(row, indexes):
    values = {
        field: row[indexes[field]].strip() if indexes.get(field) is not None and indexes[field] < len(row) else ""
        for field in (*OUTPUT_FIELDS, "updated_at")
    }
    order_id = values["order_id"].upper()
    if not order_id:
        return None
    try:
        amount, amount_currency = parse_amount(values["amount"])
        order_date = parse_order_date(values["order_date"])
    except ValueError:
        return None

    email = values["customer_email"].lower()
    if email.count("@") != 1 or not all(email.split("@")):
        email = ""

    currency = values["currency"].upper()
    currency = CURRENCY_SYMBOLS.get(currency, currency)
    if not currency:
        currency = amount_currency or "USD"

    status = values["status"].lower()
    if status == "canceled":
        status = "cancelled"
    if status not in STATUS_VALUES:
        status = "unknown"

    return (
        order_id,
        email,
        format(amount, ".2f"),
        currency,
        order_date.isoformat(),
        status,
    ), parse_updated_at(values["updated_at"])


def clean_file(input_path, output_path):
    with open(input_path, encoding="utf-8-sig", newline="") as source:
        lines = (line for line in source if line.strip() and not line.startswith("#"))
        reader = csv.reader(lines)
        try:
            header = next(reader)
        except StopIteration:
            header = []
        normalized = [normalize_header(name) for name in header]
        indexes = {
            field: normalized.index(field) if field in normalized else None
            for field in (*OUTPUT_FIELDS, "updated_at")
        }
        best_rows = {}
        for row in reader:
            cleaned = clean_row(row, indexes)
            if cleaned is None:
                continue
            output, updated_at = cleaned
            previous = best_rows.get(output[0])
            if previous is None or updated_at >= previous[0]:
                best_rows[output[0]] = (updated_at, output)

    rows = sorted(
        (entry[1] for entry in best_rows.values()),
        key=lambda row: (row[4], row[0]),
    )
    with open(output_path, "w", encoding="utf-8", newline="") as destination:
        writer = csv.writer(destination, lineterminator="\n")
        writer.writerow(OUTPUT_FIELDS)
        writer.writerows(rows)


def main(argv):
    if len(argv) != 3:
        raise SystemExit("Usage: python3 clean.py INPUT.csv OUTPUT.csv")
    clean_file(argv[1], argv[2])


if __name__ == "__main__":
    main(sys.argv)
