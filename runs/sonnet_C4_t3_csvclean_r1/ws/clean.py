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
FIELDS = ["order_id", "customer_email", "amount", "currency", "order_date", "status"]


def parse_amount(raw):
    """Return (Decimal or None, currency symbol code or '')."""
    symbol = ""
    for ch in raw:
        if ch in SYMBOLS:
            symbol = symbol or SYMBOLS[ch]
    s = "".join(ch for ch in raw if ch not in SYMBOLS and not ch.isspace())
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    if s.startswith("-"):
        negative = not negative
        s = s[1:]
    elif s.startswith("+"):
        s = s[1:]
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        if re.search(r",\d{2}$", s):
            head, tail = s.rsplit(",", 1)
            s = head.replace(",", "") + "." + tail
        else:
            s = s.replace(",", "")
    if not re.fullmatch(r"\d+(\.\d*)?|\.\d+", s):
        return None, symbol
    try:
        value = Decimal(s).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None, symbol
    if negative and value != 0:
        value = -value
    return value, symbol


def make_date(y, m, d):
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def parse_date(raw):
    s = raw.strip()
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        return make_date(m.group(1), m.group(2), m.group(3))
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        return make_date(m.group(3), m.group(2), m.group(1))
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return make_date(m.group(3), m.group(1), m.group(2))
    m = re.fullmatch(r"([A-Za-z]+) (\d{1,2}), (\d{4})", s)
    if m and m.group(1).lower() in MONTHS:
        return make_date(m.group(3), MONTHS[m.group(1).lower()], m.group(2))
    m = re.fullmatch(r"(\d{1,2}) ([A-Za-z]+) (\d{4})", s)
    if m and m.group(2).lower() in MONTHS:
        return make_date(m.group(3), MONTHS[m.group(2).lower()], m.group(1))
    return None


def parse_updated(raw):
    s = raw.strip()
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})Z?", s)
    if m:
        try:
            return datetime.strptime(m.group(1) + "T" + m.group(2), "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            pass
    return datetime.min


def clean_email(raw):
    e = raw.strip().lower()
    if e.count("@") != 1:
        return ""
    local, domain = e.split("@")
    return e if local and domain else ""


def read_lines(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [ln for ln in f if ln.strip() and ln[0] != "#"]


def main(src, dst):
    reader = csv.reader(read_lines(src))
    header = next(reader, None) or []
    index = {}
    for i, name in enumerate(header):
        key = name.strip().lower().replace(" ", "_")
        index.setdefault(key, i)

    def get(row, key):
        i = index.get(key)
        return row[i].strip() if i is not None and i < len(row) else ""

    best = {}
    for row in reader:
        order_id = get(row, "order_id").upper()
        if not order_id:
            continue
        amount, symbol = parse_amount(get(row, "amount"))
        if amount is None:
            continue
        order_date = parse_date(get(row, "order_date"))
        if order_date is None:
            continue
        currency = get(row, "currency").upper()
        currency = SYMBOLS.get(currency, currency) or symbol or "USD"
        status = get(row, "status").lower()
        if status == "canceled":
            status = "cancelled"
        if status not in STATUSES:
            status = "unknown"
        updated = parse_updated(get(row, "updated_at"))
        record = [order_id, clean_email(get(row, "customer_email")), f"{amount:.2f}",
                  currency, order_date, status]
        if order_id not in best or updated >= best[order_id][0]:
            best[order_id] = (updated, record)

    rows = sorted((r for _, r in best.values()), key=lambda r: (r[4], r[0]))
    with open(dst, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(FIELDS)
        writer.writerows(rows)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: clean.py INPUT.csv OUTPUT.csv")
    main(sys.argv[1], sys.argv[2])
