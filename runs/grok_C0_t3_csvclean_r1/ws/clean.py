#!/usr/bin/env python3
"""Clean a messy shop-order CSV export."""

import csv
import re
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

SYMBOL_TO_CURRENCY = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
}

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

ALLOWED_STATUS = {"pending", "paid", "shipped", "cancelled", "refunded"}

OUTPUT_FIELDS = [
    "order_id",
    "customer_email",
    "amount",
    "currency",
    "order_date",
    "status",
]

INPUT_FIELDS = OUTPUT_FIELDS + ["updated_at"]

# Numeric order dates. Single-digit month/day is allowed.
_RE_YMD_DASH = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})\Z")
_RE_YMD_SLASH = re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})\Z")
_RE_MDY_SLASH = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})\Z")
_RE_DMY_DOT = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})\Z")
# "Mar 4, 2026" / "March 4, 2026" — the comma is required.
_RE_MONTH_DAY = re.compile(r"([A-Za-z]+)\s+(\d{1,2})\s*,\s*(\d{4})\Z")
# "4 Mar 2026" / "4 March 2026"
_RE_DAY_MONTH = re.compile(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\Z")
# updated_at is zero-padded. Z is optional; a space may stand in for T.
_RE_UPDATED = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})Z?\Z"
)

_OLDEST = datetime.min


def norm_header(name):
    return name.replace("\ufeff", "").strip().lower().replace(" ", "_")


def read_records(path):
    """Return data rows as dicts keyed by normalised header name.

    Blank lines and lines whose first character is '#' are ignored. The first
    remaining line is the header. Missing columns read as empty strings.
    """
    lines = []
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        for line in fh:
            if line.startswith("#") or line.strip() == "":
                continue
            lines.append(line.rstrip("\r\n"))

    reader = csv.reader(lines)
    try:
        header = next(reader)
    except StopIteration:
        return []

    index = {}
    for i, cell in enumerate(header):
        key = norm_header(cell)
        if key and key not in index:
            index[key] = i

    records = []
    for rec in reader:
        row = {}
        for name in INPUT_FIELDS:
            pos = index.get(name)
            if pos is None or pos >= len(rec):
                row[name] = ""
            else:
                row[name] = rec[pos].strip()
        records.append(row)
    return records


def parse_amount(raw):
    """Parse a messy amount into a Decimal, or return None.

    Currency symbols and whitespace are removed. Parentheses and a leading
    minus mark a negative value. Separator rule: if both '.' and ',' appear,
    the one that appears last is the decimal separator and the other is a
    thousands separator. If only ',' appears and exactly two digits follow
    the last ',', it is the decimal separator; otherwise ',' is a thousands
    separator. If only '.' appears it is the decimal separator.
    """
    cleaned = "".join(
        ch for ch in raw if ch not in SYMBOL_TO_CURRENCY and not ch.isspace()
    )
    if not cleaned:
        return None

    negative = False
    while cleaned and (
        cleaned[0] in "+-" or (cleaned[0] == "(" and cleaned[-1] == ")")
    ):
        if cleaned[0] == "+":
            cleaned = cleaned[1:]
        elif cleaned[0] == "-":
            negative = True
            cleaned = cleaned[1:]
        else:
            negative = True
            cleaned = cleaned[1:-1]
    if not cleaned or not re.search(r"\d", cleaned):
        return None

    has_dot = "." in cleaned
    has_comma = "," in cleaned
    if has_dot and has_comma:
        if cleaned.rfind(".") > cleaned.rfind(","):
            decimal_sep, thousands_sep = ".", ","
        else:
            decimal_sep, thousands_sep = ",", "."
        cleaned = cleaned.replace(thousands_sep, "")
        if cleaned.count(decimal_sep) != 1:
            return None
        int_part, frac_part = cleaned.split(decimal_sep)
    elif has_comma:
        last = cleaned.rfind(",")
        after = cleaned[last + 1 :]
        if len(after) == 2 and after.isdigit():
            int_part = cleaned[:last].replace(",", "")
            frac_part = after
        else:
            int_part = cleaned.replace(",", "")
            frac_part = ""
    elif has_dot:
        if cleaned.count(".") != 1:
            return None
        int_part, frac_part = cleaned.split(".")
    else:
        int_part, frac_part = cleaned, ""

    if int_part == "":
        int_part = "0"
    if not int_part.isdigit():
        return None
    if frac_part and not frac_part.isdigit():
        return None

    number = int_part if not frac_part else int_part + "." + frac_part
    try:
        value = Decimal(number)
    except InvalidOperation:
        return None
    if negative:
        value = -value
    return value


def format_amount(value):
    """Exactly two decimals, half away from zero."""
    quantized = abs(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if quantized == 0:
        return "0.00"
    text = format(quantized, ".2f")
    if value < 0:
        return "-" + text
    return text


def normalize_currency(currency, amount_raw):
    text = currency.strip()
    if text in SYMBOL_TO_CURRENCY:
        return SYMBOL_TO_CURRENCY[text]
    if text == "":
        for ch in amount_raw:
            mapped = SYMBOL_TO_CURRENCY.get(ch)
            if mapped:
                return mapped
        return "USD"
    return text.upper()


def normalize_email(email):
    text = email.strip().lower()
    if text.count("@") != 1:
        return ""
    local, domain = text.split("@")
    if not local or not domain:
        return ""
    return text


def _make_date(year, month, day):
    try:
        return datetime(year, month, day).date()
    except ValueError:
        return None


def parse_order_date(raw):
    text = raw.strip()
    if not text:
        return None

    match = _RE_YMD_DASH.fullmatch(text)
    if match:
        year, month, day = (int(g) for g in match.groups())
        return _make_date(year, month, day)

    match = _RE_YMD_SLASH.fullmatch(text)
    if match:
        year, month, day = (int(g) for g in match.groups())
        return _make_date(year, month, day)

    match = _RE_MDY_SLASH.fullmatch(text)
    if match:
        month, day, year = (int(g) for g in match.groups())
        return _make_date(year, month, day)

    match = _RE_DMY_DOT.fullmatch(text)
    if match:
        day, month, year = (int(g) for g in match.groups())
        return _make_date(year, month, day)

    match = _RE_MONTH_DAY.fullmatch(text)
    if match:
        month = MONTHS.get(match.group(1).lower())
        if month is None:
            return None
        return _make_date(int(match.group(3)), month, int(match.group(2)))

    match = _RE_DAY_MONTH.fullmatch(text)
    if match:
        month = MONTHS.get(match.group(2).lower())
        if month is None:
            return None
        return _make_date(int(match.group(3)), month, int(match.group(1)))

    return None


def parse_updated_at(raw):
    """Timestamp used only for de-duplication. Empty or invalid is oldest."""
    text = raw.strip()
    if not text:
        return _OLDEST
    match = _RE_UPDATED.fullmatch(text)
    if not match:
        return _OLDEST
    parts = [int(g) for g in match.groups()]
    try:
        return datetime(*parts)
    except ValueError:
        return _OLDEST


def normalize_status(status):
    text = status.strip().lower()
    if text == "canceled":
        text = "cancelled"
    if text not in ALLOWED_STATUS:
        return "unknown"
    return text


def clean(input_path, output_path):
    with localcontext() as ctx:
        ctx.prec = 50
        ctx.rounding = ROUND_HALF_UP
        best = {}
        for row in read_records(input_path):
            order_id = row["order_id"].strip().upper()
            if not order_id:
                continue

            amount = parse_amount(row["amount"])
            if amount is None:
                continue

            order_date = parse_order_date(row["order_date"])
            if order_date is None:
                continue

            updated = parse_updated_at(row["updated_at"])
            output = [
                order_id,
                normalize_email(row["customer_email"]),
                format_amount(amount),
                normalize_currency(row["currency"], row["amount"]),
                order_date.strftime("%Y-%m-%d"),
                normalize_status(row["status"]),
            ]
            previous = best.get(order_id)
            # Later updated_at wins; on a tie the later file row wins.
            if previous is None or updated >= previous[0]:
                best[order_id] = (updated, output)

        rows = [item[1] for item in best.values()]
        rows.sort(key=lambda item: (item[4], item[0]))

    with open(output_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(OUTPUT_FIELDS)
        writer.writerows(rows)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: python3 clean.py INPUT.csv OUTPUT.csv\n")
        return 1
    clean(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
