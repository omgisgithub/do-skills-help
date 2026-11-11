import csv
import re
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
MONTHS = {}
for _i, _n in enumerate(["january", "february", "march", "april", "may", "june", "july",
                         "august", "september", "october", "november", "december"], 1):
    MONTHS[_n] = _i
    MONTHS[_n[:3]] = _i
MONTHS["sept"] = 9


def make_date(y, m, d):
    try:
        return datetime(int(y), int(m), int(d)).strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_date(s):
    s = s.strip()
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        return make_date(m.group(1), m.group(2), m.group(3))
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        return make_date(m.group(3), m.group(2), m.group(1))
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return make_date(m.group(3), m.group(1), m.group(2))
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", s)
    if m and m.group(1).lower() in MONTHS:
        return make_date(m.group(3), MONTHS[m.group(1).lower()], m.group(2))
    m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)
    if m and m.group(2).lower() in MONTHS:
        return make_date(m.group(3), MONTHS[m.group(2).lower()], m.group(1))
    return None


def parse_amount(raw):
    """Return (Decimal or None, symbol currency or None)."""
    sym = None
    for ch in raw:
        if ch in SYMBOLS:
            sym = SYMBOLS[ch]
            break
    s = re.sub(r"[$€£\s]", "", raw)
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    if s.startswith("-"):
        neg = True
        s = s[1:]
    if not s or not re.fullmatch(r"[0-9.,]+", s) or not re.search(r"\d", s):
        return None, sym
    if "." in s and "," in s:
        if s.rfind(".") > s.rfind(","):
            dec, thou = ".", ","
        else:
            dec, thou = ",", "."
    elif "," in s:
        if re.fullmatch(r"\d{2}", s.rsplit(",", 1)[1]):
            dec, thou = ",", "."
        else:
            dec, thou = None, ","
    else:
        dec, thou = ".", ","
    s = s.replace(thou, "")
    if dec == ",":
        s = s.replace(",", ".")
    if s.count(".") > 1:
        return None, sym
    try:
        val = Decimal(s)
    except InvalidOperation:
        return None, sym
    if not val.is_finite():
        return None, sym
    val = val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if neg:
        val = -val
    if val == 0:
        val = abs(val)
    return val, sym


def parse_updated(s):
    s = s.strip()
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})Z?", s)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + "T" + m.group(2), "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def clean_email(s):
    s = s.strip().lower()
    parts = s.split("@")
    if len(parts) == 2 and parts[0] and parts[1]:
        return s
    return ""


def main(inp, out):
    with open(inp, encoding="utf-8-sig", newline="") as f:
        lines = [l for l in f.read().splitlines(True)
                 if l.strip() and not l.startswith("#")]
    reader = csv.reader(lines)
    try:
        header = next(reader)
    except StopIteration:
        header = []
    names = [h.strip().lower().replace(" ", "_") for h in header]
    idx = {}
    for i, n in enumerate(names):
        idx.setdefault(n, i)

    def get(row, name):
        i = idx.get(name)
        if i is None or i >= len(row):
            return ""
        return row[i].strip()

    best = {}
    for pos, row in enumerate(reader):
        oid = get(row, "order_id").upper()
        if not oid:
            continue
        amount, sym = parse_amount(get(row, "amount"))
        if amount is None:
            continue
        date = parse_date(get(row, "order_date"))
        if date is None:
            continue
        cur = get(row, "currency").upper()
        cur = SYMBOLS.get(cur, cur)
        if not cur:
            cur = sym or "USD"
        status = get(row, "status").lower()
        if status == "canceled":
            status = "cancelled"
        if status not in STATUSES:
            status = "unknown"
        upd = parse_updated(get(row, "updated_at")) or datetime.min
        rec = (oid, clean_email(get(row, "customer_email")), format(amount, "f"),
               cur, date, status)
        key = (upd, pos)
        if oid not in best or key >= best[oid][0]:
            best[oid] = (key, rec)

    rows = sorted((r for _, r in best.values()), key=lambda r: (r[4], r[0]))
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["order_id", "customer_email", "amount", "currency", "order_date", "status"])
        w.writerows(rows)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
