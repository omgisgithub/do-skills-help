"""Clean a messy order export: python3 clean.py INPUT.csv OUTPUT.csv"""

import csv
import re
import sys
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

OUTPUT_COLUMNS = ["order_id", "customer_email", "amount", "currency", "order_date", "status"]
CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
MONTHS = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]
MONTH_NUMBERS = {}
for number, name in enumerate(MONTHS, start=1):
    MONTH_NUMBERS[name] = number
    MONTH_NUMBERS[name[:3]] = number

# Named groups; the first pattern that fully matches decides the field order.
DATE_FORMS = [
    re.compile(r"(?P<y>\d{4})[-/](?P<m>\d{1,2})[-/](?P<d>\d{1,2})"),
    re.compile(r"(?P<d>\d{1,2})\.(?P<m>\d{1,2})\.(?P<y>\d{4})"),
    re.compile(r"(?P<m>\d{1,2})/(?P<d>\d{1,2})/(?P<y>\d{4})"),
    re.compile(r"(?P<mon>[a-z]+) (?P<d>\d{1,2}), (?P<y>\d{4})"),
    re.compile(r"(?P<d>\d{1,2}) (?P<mon>[a-z]+) (?P<y>\d{4})"),
]
UPDATED_AT = re.compile(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})Z?")
OLDEST = datetime.min


def parse_amount(text):
    """Return the amount as a Decimal rounded to 2 places, or None if unparseable."""
    text = re.sub(r"[\s$€£]", "", text)
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative, text = True, text[1:-1]
    elif text.startswith("-"):
        negative, text = True, text[1:]

    if "," in text and "." in text:
        decimal = "." if text.rfind(".") > text.rfind(",") else ","
    elif "," in text and re.search(r",\d{2}$", text):
        decimal = ","
    elif "." in text:
        decimal = "."
    else:
        decimal = None

    if decimal == ",":
        head, _, tail = text.rpartition(",")
        text = head.replace(",", "").replace(".", "") + "." + tail
    else:
        text = text.replace(",", "")

    if not re.fullmatch(r"\d+\.?\d*|\.\d+", text):
        return None
    try:
        value = Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None
    if negative:
        value = -value
    return abs(value) if value == 0 else value


def parse_date(text):
    """Return the date as YYYY-MM-DD, or None if it is not one of the accepted forms."""
    text = text.strip().lower()
    for form in DATE_FORMS:
        match = form.fullmatch(text)
        if match is None:
            continue
        fields = match.groupdict()
        if "mon" in fields:
            month = MONTH_NUMBERS.get(fields["mon"])
            if month is None:
                return None
        else:
            month = int(fields["m"])
        try:
            return date(int(fields["y"]), month, int(fields["d"])).isoformat()
        except ValueError:
            return None
    return None


def parse_updated_at(text):
    """Return the timestamp for de-duplication; empty or unreadable values count as oldest."""
    match = UPDATED_AT.fullmatch(text.strip())
    if match is None:
        return OLDEST
    try:
        return datetime.strptime(" ".join(match.groups()), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return OLDEST


def clean_email(text):
    local, sep, domain = text.strip().lower().partition("@")
    if sep and local and domain and "@" not in domain:
        return local + "@" + domain
    return ""


def clean_currency(field, amount_text):
    field = field.strip()
    if field:
        return CURRENCY_SYMBOLS.get(field, field.upper())
    symbol = next((ch for ch in amount_text if ch in CURRENCY_SYMBOLS), None)
    return CURRENCY_SYMBOLS.get(symbol, "USD")


def clean_status(text):
    status = text.strip().lower()
    if status == "canceled":
        status = "cancelled"
    return status if status in STATUSES else "unknown"


def clean_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        # Blank and '#' lines are skipped before CSV parsing.
        lines = [line for line in f if line.strip() and not line.startswith("#")]
    reader = csv.reader(lines)
    columns = {}
    for index, name in enumerate(next(reader, [])):
        columns.setdefault(name.strip().lower().replace(" ", "_"), index)

    def field(row, name):
        index = columns.get(name)
        if index is None or index >= len(row):
            return ""
        return row[index]

    latest = {}  # order_id -> (updated_at, record)
    for row in reader:
        order_id = field(row, "order_id").strip().upper()
        if not order_id:
            continue
        amount_text = field(row, "amount")
        amount = parse_amount(amount_text)
        if amount is None:
            continue
        order_date = parse_date(field(row, "order_date"))
        if order_date is None:
            continue
        updated_at = parse_updated_at(field(row, "updated_at"))
        record = {
            "order_id": order_id,
            "customer_email": clean_email(field(row, "customer_email")),
            "amount": f"{amount:.2f}",
            "currency": clean_currency(field(row, "currency"), amount_text),
            "order_date": order_date,
            "status": clean_status(field(row, "status")),
        }
        # ">=" so that on a tie the later row in the file wins.
        kept = latest.get(order_id)
        if kept is None or updated_at >= kept[0]:
            latest[order_id] = (updated_at, record)

    records = [record for _, record in latest.values()]
    records.sort(key=lambda record: (record["order_date"], record["order_id"]))
    return records


def write_rows(path, records):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def main():
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} INPUT.csv OUTPUT.csv")
    write_rows(sys.argv[2], clean_rows(sys.argv[1]))


if __name__ == "__main__":
    main()
