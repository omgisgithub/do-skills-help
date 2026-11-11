#!/usr/bin/env python3
"""Clean a messy order export CSV.

Usage: python3 clean.py INPUT.csv OUTPUT.csv
"""
import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}

MONTHS = {}
for _number, _name in enumerate(
    "january february march april may june july august september october november december".split(),
    1,
):
    MONTHS[_name] = _number
    MONTHS[_name[:3]] = _number
MONTHS["sept"] = 9

HEADER = ["order_id", "customer_email", "amount", "currency", "order_date", "status"]


def parse_amount(raw):
    """Return a 2-decimal Decimal, or None when the value is unparseable."""
    s = raw.strip()
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    for symbol in SYMBOLS:
        s = s.replace(symbol, "")
    s = re.sub(r"\s+", "", s)
    if not s:
        return None
    if s.startswith("-"):
        negative = True
        s = s[1:]
    elif s.startswith("+"):
        s = s[1:]

    if "." in s and "," in s:
        if s.rfind(".") > s.rfind(","):
            s = s.replace(",", "")
        else:
            i = s.rfind(",")
            s = s[:i].replace(",", "").replace(".", "") + "." + s[i + 1:]
    elif "," in s:
        i = s.rfind(",")
        if len(s) - i - 1 == 2:
            s = s[:i].replace(",", "") + "." + s[i + 1:]
        else:
            s = s.replace(",", "")

    if not re.fullmatch(r"\d+(\.\d*)?|\.\d+", s):
        return None
    try:
        value = Decimal(s)
        if negative:
            value = -value
        value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None
    if value == 0:
        value = abs(value)  # avoid -0.00
    return value


def parse_date(raw):
    """Return a date or None for missing/invalid values."""
    s = raw.strip()
    if not s:
        return None
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        y, mo, d = (int(part) for part in m.groups())
    else:
        m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
        if m:
            d, mo, y = (int(part) for part in m.groups())
        else:
            m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
            if m:
                mo, d, y = (int(part) for part in m.groups())
            else:
                m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2})\s*,\s*(\d{4})", s)
                if m:
                    mo = MONTHS.get(m.group(1).lower())
                    d, y = int(m.group(2)), int(m.group(3))
                else:
                    m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)
                    if not m:
                        return None
                    d = int(m.group(1))
                    mo = MONTHS.get(m.group(2).lower())
                    y = int(m.group(3))
    if mo is None:
        return None
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def parse_updated(raw):
    """Return the timestamp, or the oldest possible for missing/invalid ones."""
    s = raw.strip()
    if s.endswith("Z"):
        s = s[:-1]
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return datetime.min


def clean(input_path, output_path):
    with open(input_path, encoding="utf-8-sig", newline="") as f:
        text = f.read()

    lines = [line for line in text.splitlines() if line.strip() and not line.startswith("#")]
    rows = csv.reader(lines)
    try:
        header = next(rows)
    except StopIteration:
        header = []

    index = {}
    for i, name in enumerate(header):
        index.setdefault(name.strip().lower().replace(" ", "_"), i)

    def value(row, name):
        i = index.get(name)
        return row[i].strip() if i is not None and i < len(row) else ""

    kept = {}
    for row in rows:
        order_id = value(row, "order_id").upper()
        if not order_id:
            continue
        amount_raw = value(row, "amount")
        amount = parse_amount(amount_raw)
        if amount is None:
            continue
        order_date = parse_date(value(row, "order_date"))
        if order_date is None:
            continue

        email = value(row, "customer_email").lower()
        if email.count("@") != 1 or not all(email.split("@")):
            email = ""

        currency_raw = value(row, "currency").upper()
        for symbol, code in SYMBOLS.items():
            currency_raw = currency_raw.replace(symbol, code)
        currency = currency_raw
        if not currency:
            currency = next(
                (SYMBOLS[ch] for ch in amount_raw if ch in SYMBOLS), "USD"
            )

        status = value(row, "status").lower()
        if status == "canceled":
            status = "cancelled"
        if status not in STATUSES:
            status = "unknown"

        output_row = [
            order_id,
            email,
            f"{amount:.2f}",
            currency,
            order_date.isoformat(),
            status,
        ]
        updated = parse_updated(value(row, "updated_at"))
        previous = kept.get(order_id)
        if previous is None or updated >= previous[0]:
            kept[order_id] = (updated, output_row)

    result = [row for _, row in kept.values()]
    result.sort(key=lambda row: (row[4], row[0]))

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(HEADER)
        writer.writerows(result)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python3 clean.py INPUT.csv OUTPUT.csv")
    clean(sys.argv[1], sys.argv[2])
