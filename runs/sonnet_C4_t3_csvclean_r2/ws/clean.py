"""Clean a messy order export CSV."""
import csv
import re
import sys
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
MONTHS = {}
for _i, _name in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1):
    MONTHS[_name] = _i
    MONTHS[_name[:3]] = _i
OUT_HEADER = ["order_id", "customer_email", "amount", "currency", "order_date", "status"]


def parse_amount(raw):
    """Return (Decimal, symbol_currency_or_None), or (None, None) if unparseable."""
    text = raw.strip()
    symbol = next((SYMBOLS[c] for c in text if c in SYMBOLS), None)
    for c in SYMBOLS:
        text = text.replace(c, "")
    text = re.sub(r"\s+", "", text)
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    if text.startswith("-"):
        negative = not negative
        text = text[1:]
    elif text.startswith("+"):
        text = text[1:]
    if not text or not re.fullmatch(r"[0-9.,]+", text):
        return None, None
    if "." in text and "," in text:
        dec = "." if text.rfind(".") > text.rfind(",") else ","
    elif "," in text:
        dec = "," if re.fullmatch(r"[0-9.,]*,[0-9]{2}", text) else None
    elif "." in text:
        dec = "."
    else:
        dec = None
    if dec:
        head, _, tail = text.rpartition(dec)
        other = "," if dec == "." else "."
        if dec in head or not tail.isdigit() and tail:
            return None, None
        text = head.replace(other, "").replace(dec, "") + "." + tail
    else:
        text = text.replace(",", "").replace(".", "")
    if not re.fullmatch(r"[0-9]*\.?[0-9]*", text) or not re.search(r"[0-9]", text):
        return None, None
    try:
        value = Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None, None
    if negative and value:
        value = -value
    return value, symbol


def parse_date(raw):
    """Return an ISO date string or None."""
    text = raw.strip()
    y = m = d = None
    if (g := re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)):
        y, m, d = g.groups()
    elif (g := re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)):
        d, m, y = g.groups()
    elif (g := re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)):
        m, d, y = g.groups()
    elif (g := re.fullmatch(r"([A-Za-z]+) (\d{1,2}), (\d{4})", text)):
        m, d, y = g.groups()
        m = MONTHS.get(m.lower())
    elif (g := re.fullmatch(r"(\d{1,2}) ([A-Za-z]+) (\d{4})", text)):
        d, m, y = g.groups()
        m = MONTHS.get(m.lower())
    if m is None or y is None:
        return None
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def parse_updated(raw):
    """Return a datetime for ordering; oldest possible when empty/invalid."""
    g = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})Z?", raw.strip())
    if g:
        try:
            return datetime.fromisoformat(f"{g.group(1)}T{g.group(2)}")
        except ValueError:
            pass
    return datetime.min


def clean_email(raw):
    email = raw.strip().lower()
    if email.count("@") != 1:
        return ""
    local, domain = email.split("@")
    return email if local and domain else ""


def clean_row(row):
    """Return (output_row, updated_at) or None if the row is dropped."""
    order_id = row.get("order_id", "").strip().upper()
    if not order_id:
        return None
    amount, symbol = parse_amount(row.get("amount", ""))
    if amount is None:
        return None
    order_date = parse_date(row.get("order_date", ""))
    if order_date is None:
        return None
    currency = row.get("currency", "").strip().upper()
    currency = SYMBOLS.get(currency, currency) or symbol or "USD"
    status = row.get("status", "").strip().lower()
    if status == "canceled":
        status = "cancelled"
    if status not in STATUSES:
        status = "unknown"
    out = [order_id, clean_email(row.get("customer_email", "")), f"{amount:.2f}",
           currency, order_date, status]
    return out, parse_updated(row.get("updated_at", ""))


def main(src, dst):
    with open(src, encoding="utf-8-sig", newline="") as f:
        lines = [ln for ln in f if ln.strip() and not ln.startswith("#")]
    reader = csv.reader(lines)
    header = next(reader, [])
    names = [re.sub(" ", "_", h.strip().lower()) for h in header]
    best = {}
    for fields in reader:
        if not any(x.strip() for x in fields):
            continue
        row = {n: v for n, v in zip(names, fields)}
        result = clean_row(row)
        if result is None:
            continue
        out, updated = result
        prev = best.get(out[0])
        if prev is None or updated >= prev[1]:
            best[out[0]] = (out, updated)
    rows = sorted((v[0] for v in best.values()), key=lambda r: (r[4], r[0]))
    with open(dst, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(OUT_HEADER)
        w.writerows(rows)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: clean.py INPUT.csv OUTPUT.csv")
    main(sys.argv[1], sys.argv[2])
