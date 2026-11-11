#!/usr/bin/env python3
"""Clean a messy order export CSV.

Usage: python3 clean.py INPUT.csv OUTPUT.csv
"""
import csv
import re
import sys
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

OUT_HEADER = ["order_id", "customer_email", "amount", "currency", "order_date", "status"]
ALLOWED_STATUS = {"pending", "paid", "shipped", "cancelled", "refunded"}
SYMBOL_CURRENCY = {"$": "USD", "€": "EUR", "£": "GBP"}

MONTHS = {}
for _num, _name in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"],
    start=1,
):
    MONTHS[_name] = _num
    MONTHS[_name[:3]] = _num
MONTHS["sept"] = 9

_ISO_RE = re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})")
_DMY_DOT_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")
_MDY_SLASH_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
_MONTH_FIRST_RE = re.compile(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})")
_DAY_FIRST_RE = re.compile(r"(\d{1,2})\s+([A-Za-z]+),?\s+(\d{4})")
_NUMBER_RE = re.compile(r"\d+(?:\.\d*)?|\.\d+")
_UPDATED_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})Z?")


def clean_amount(text):
    """Return the amount as a Decimal rounded to 2 places, or None if unparseable."""
    s = re.sub(r"[\s$€£]", "", text)
    neg = False
    m = re.fullmatch(r"\((.*)\)", s)
    if m:
        neg, s = True, m[1]
    elif s[:1] == "-":
        neg, s = True, s[1:]
    elif s[:1] == "+":
        s = s[1:]
    s = _plain_number(s)
    if not s or not _NUMBER_RE.fullmatch(s):
        return None
    try:
        value = Decimal(s).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None
    if neg and value != 0:
        value = -value
    return value


def _plain_number(s):
    """Turn digits with separators into digits with '.' as the decimal point, or None."""
    has_dot, has_comma = "." in s, "," in s
    if has_dot and has_comma:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
    elif has_comma:
        if len(s) - s.rfind(",") - 1 != 2:
            return s.replace(",", "")  # every comma is a thousands separator
        head, tail = s.rsplit(",", 1)
        return head.replace(",", "") + "." + tail
    elif has_dot:
        dec = "."
    else:
        return s
    thousands = "," if dec == "." else "."
    s = s.replace(thousands, "")
    if s.count(dec) != 1:
        return None
    return s.replace(dec, ".")


def clean_currency(field, amount_raw):
    code = field.strip().upper()
    if code in SYMBOL_CURRENCY:
        return SYMBOL_CURRENCY[code]
    if code:
        return code
    for ch in amount_raw:
        if ch in SYMBOL_CURRENCY:
            return SYMBOL_CURRENCY[ch]
    return "USD"


def clean_email(text):
    s = text.strip().lower()
    local, sep, domain = s.partition("@")
    if sep and "@" not in domain and local.strip() and domain.strip():
        return s
    return ""


def clean_status(text):
    s = text.strip().lower()
    if s == "canceled":
        s = "cancelled"
    return s if s in ALLOWED_STATUS else "unknown"


def _date_parts(s):
    m = _ISO_RE.fullmatch(s)
    if m:
        return int(m[1]), int(m[2]), int(m[3])
    m = _DMY_DOT_RE.fullmatch(s)
    if m:
        return int(m[3]), int(m[2]), int(m[1])
    m = _MDY_SLASH_RE.fullmatch(s)
    if m:
        return int(m[3]), int(m[1]), int(m[2])
    m = _MONTH_FIRST_RE.fullmatch(s)
    if m and m[1].lower() in MONTHS:
        return int(m[3]), MONTHS[m[1].lower()], int(m[2])
    m = _DAY_FIRST_RE.fullmatch(s)
    if m and m[2].lower() in MONTHS:
        return int(m[3]), MONTHS[m[2].lower()], int(m[1])
    return None


def clean_date(text):
    parts = _date_parts(text.strip())
    if parts is None:
        return None
    try:
        return date(*parts).isoformat()
    except ValueError:
        return None


def parse_updated(text):
    """Sort key for updated_at; empty or unparseable values sort as oldest."""
    m = _UPDATED_RE.fullmatch(text.strip())
    if not m:
        return datetime.min
    try:
        return datetime(*map(int, m.groups()))
    except ValueError:
        return datetime.min


def main(argv):
    if len(argv) != 3:
        print("usage: python3 clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2
    src, dst = argv[1], argv[2]

    with open(src, encoding="utf-8-sig", newline="") as f:
        lines = [ln for ln in f if ln.strip() and not ln.startswith("#")]
    reader = csv.reader(lines)

    columns = {}
    for i, name in enumerate(next(reader, [])):
        columns.setdefault(re.sub(r"\s+", "_", name.strip().lower()), i)

    def get(row, col):
        i = columns.get(col)
        if i is None or i >= len(row):
            return ""
        return row[i].strip()

    best = {}  # order_id -> (rank, output row); rank = (updated_at, file position)
    for position, row in enumerate(reader):
        order_id = get(row, "order_id").upper()
        if not order_id:
            continue
        amount_raw = get(row, "amount")
        amount = clean_amount(amount_raw)
        if amount is None:
            continue
        order_date = clean_date(get(row, "order_date"))
        if order_date is None:
            continue

        out = [
            order_id,
            clean_email(get(row, "customer_email")),
            str(amount),
            clean_currency(get(row, "currency"), amount_raw),
            order_date,
            clean_status(get(row, "status")),
        ]
        rank = (parse_updated(get(row, "updated_at")), position)
        if order_id not in best or rank > best[order_id][0]:
            best[order_id] = (rank, out)

    rows = sorted((out for _, out in best.values()), key=lambda r: (r[4], r[0]))
    with open(dst, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(OUT_HEADER)
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
