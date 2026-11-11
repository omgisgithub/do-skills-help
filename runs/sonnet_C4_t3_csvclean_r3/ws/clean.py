"""Clean a messy order export CSV."""
import csv
import re
import sys
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
MONTHS = {
    m: i + 1
    for i, m in enumerate(
        "january february march april may june july august "
        "september october november december".split()
    )
}
MONTHS.update({name[:3]: num for name, num in list(MONTHS.items())})
MONTHS["sept"] = 9

FIELDS = ["order_id", "customer_email", "amount", "currency", "order_date", "status"]
OLDEST = datetime.min


def make_date(year, month, day):
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def parse_date(text):
    text = text.strip()
    flags = re.ASCII
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text, flags)
    if m:
        return make_date(m[1], m[2], m[3])
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text, flags)
    if m:
        return make_date(m[3], m[2], m[1])
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text, flags)
    if m:
        return make_date(m[3], m[1], m[2])
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", text, flags)
    if m and m[1].lower() in MONTHS:
        return make_date(m[3], MONTHS[m[1].lower()], m[2])
    m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text, flags)
    if m and m[2].lower() in MONTHS:
        return make_date(m[3], MONTHS[m[2].lower()], m[1])
    return None


def parse_amount(text):
    """Return (formatted amount or None, currency from symbol or '')."""
    symbol_currency = ""
    for ch in text:
        if ch in SYMBOLS:
            symbol_currency = SYMBOLS[ch]
            break
    s = re.sub(r"[$€£\s]", "", text)
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    if s.startswith("-"):
        negative = not negative
        s = s[1:]
    if "." in s and "," in s:
        if s.rfind(".") > s.rfind(","):
            s = s.replace(",", "")
        else:
            s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        if re.fullmatch(r"\d{2}", s[s.rfind(",") + 1:]):
            head, tail = s.rsplit(",", 1)
            s = head.replace(",", "") + "." + tail
        else:
            s = s.replace(",", "")
    if not re.fullmatch(r"(\d+(\.\d*)?|\.\d+)", s, re.ASCII):
        return None, symbol_currency
    try:
        value = Decimal(s)
    except InvalidOperation:
        return None, symbol_currency
    value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if negative and value != 0:
        value = -value
    return f"{value:.2f}", symbol_currency


def clean_email(text):
    text = text.strip().lower()
    parts = text.split("@")
    if len(parts) == 2 and parts[0] and parts[1]:
        return text
    return ""


def parse_updated(text):
    text = text.strip()
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})Z?", text, re.ASCII)
    if not m:
        return OLDEST
    try:
        return datetime.strptime(f"{m[1]}T{m[2]}", "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return OLDEST


def clean_row(row):
    order_id = row.get("order_id", "").strip().upper()
    if not order_id:
        return None
    amount, symbol_currency = parse_amount(row.get("amount", ""))
    if amount is None:
        return None
    order_date = parse_date(row.get("order_date", ""))
    if order_date is None:
        return None
    currency = row.get("currency", "").strip().upper()
    currency = SYMBOLS.get(currency, currency) or symbol_currency or "USD"
    status = row.get("status", "").strip().lower()
    if status == "canceled":
        status = "cancelled"
    if status not in STATUSES:
        status = "unknown"
    return {
        "order_id": order_id,
        "customer_email": clean_email(row.get("customer_email", "")),
        "amount": amount,
        "currency": currency,
        "order_date": order_date,
        "status": status,
    }


def read_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        lines = [ln for ln in f if ln.strip() and not ln.startswith("#")]
    reader = csv.reader(lines)
    header = next(reader, None)
    if header is None:
        return
    names = [re.sub(r" ", "_", h.strip().lower()) for h in header]
    for values in reader:
        row = {}
        for name, value in zip(names, values):
            row.setdefault(name, value)
        yield row


def main(argv):
    if len(argv) != 3:
        print("usage: clean.py INPUT.csv OUTPUT.csv", file=sys.stderr)
        return 2
    best = {}
    for row in read_rows(argv[1]):
        cleaned = clean_row(row)
        if cleaned is None:
            continue
        updated = parse_updated(row.get("updated_at", ""))
        key = cleaned["order_id"]
        if key not in best or updated >= best[key][0]:
            best[key] = (updated, cleaned)
    rows = sorted((c for _, c in best.values()), key=lambda r: (r["order_date"], r["order_id"]))
    with open(argv[2], "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(FIELDS)
        for r in rows:
            writer.writerow([r[k] for k in FIELDS])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
