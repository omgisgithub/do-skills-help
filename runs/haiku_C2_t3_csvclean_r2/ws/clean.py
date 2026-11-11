#!/usr/bin/env python3
"""Clean a messy order export: python3 clean.py INPUT.csv OUTPUT.csv"""
import calendar
import csv
import re
import sys
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

OUT_FIELDS = ["order_id", "customer_email", "amount", "currency", "order_date", "status"]
SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.lower(): i for i, name in enumerate(calendar.month_abbr) if name})


def parse_amount(text):
    """Return (amount rounded to cents, currency from a symbol in the text) or None."""
    symbol = next((SYMBOLS[c] for c in text if c in SYMBOLS), "")
    s = re.sub(r"[\s$€£()]", "", text)
    negative = "(" in text or s.startswith("-")
    s = s.lstrip("-")
    if "," in s and "." in s:
        comma_is_decimal = s.rfind(",") > s.rfind(".")
    elif "," in s:
        comma_is_decimal = len(s) - s.rfind(",") == 3  # exactly two digits after the comma
    else:
        comma_is_decimal = False
    if comma_is_decimal:
        head, _, tail = s.replace(".", "").rpartition(",")
        s = head.replace(",", "") + "." + tail
    else:
        s = s.replace(",", "")
    if not re.fullmatch(r"\d+(\.\d*)?|\.\d+", s):
        return None
    value = Decimal(s).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return (-value if negative and value else value), symbol


def parse_date(text):
    """Return YYYY-MM-DD for the accepted input forms, or None."""
    text = text.lower()
    if m := re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text):
        y, mo, d = m.groups()
    elif m := re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text):
        d, mo, y = m.groups()
    elif m := re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text):
        mo, d, y = m.groups()
    elif m := re.fullmatch(r"([a-z]+) (\d{1,2}), (\d{4})", text):
        name, d, y = m.groups()
        mo = MONTHS.get(name)
    elif m := re.fullmatch(r"(\d{1,2}) ([a-z]+) (\d{4})", text):
        d, name, y = m.groups()
        mo = MONTHS.get(name)
    else:
        return None
    try:
        return date(int(y), int(mo), int(d)).isoformat()
    except (TypeError, ValueError):
        return None


def main(src, dst):
    with open(src, encoding="utf-8-sig", newline="") as f:
        lines = [line for line in f if line.strip() and not line.startswith("#")]
    reader = csv.reader(lines)
    header = ["_".join(h.lower().split()) for h in next(reader, [])]

    best = {}  # order_id -> (updated_at key, row); later rows win ties
    for row in reader:
        rec = {n: v.strip() for n, v in zip(header, row + [""] * len(header))}
        oid = rec.get("order_id", "").upper()
        parsed = parse_amount(rec.get("amount", ""))
        order_date = parse_date(rec.get("order_date", ""))
        if not oid or parsed is None or order_date is None:
            continue
        amount, symbol_currency = parsed

        email = rec.get("customer_email", "").lower()
        parts = email.split("@")
        if len(parts) != 2 or not all(parts):
            email = ""

        currency = rec.get("currency", "").upper()
        currency = SYMBOLS.get(currency, currency) or symbol_currency or "USD"

        status = rec.get("status", "").lower()
        status = "cancelled" if status == "canceled" else status
        if status not in STATUSES:
            status = "unknown"

        updated = rec.get("updated_at", "")
        key = ""
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}Z?", updated):
            key = updated.replace(" ", "T").removesuffix("Z")

        out = {
            "order_id": oid,
            "customer_email": email,
            "amount": f"{amount:.2f}",
            "currency": currency,
            "order_date": order_date,
            "status": status,
        }
        if oid not in best or key >= best[oid][0]:
            best[oid] = (key, out)

    rows = sorted((r for _, r in best.values()), key=lambda r: (r["order_date"], r["order_id"]))
    with open(dst, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python3 clean.py INPUT.csv OUTPUT.csv")
    main(sys.argv[1], sys.argv[2])
