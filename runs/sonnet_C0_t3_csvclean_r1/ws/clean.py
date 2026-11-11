import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
MONTHS = {m: i + 1 for i, m in enumerate(
    "january february march april may june july august september october november december".split())}
for _k, _v in list(MONTHS.items()):
    MONTHS[_k[:3]] = _v
MONTHS["sept"] = 9


def mkdate(y, m, d):
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def parse_date(s):
    s = s.strip()
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        return mkdate(m[1], m[2], m[3])
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        return mkdate(m[3], m[2], m[1])
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return mkdate(m[3], m[1], m[2])
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", s)
    if m and m[1].lower() in MONTHS:
        return mkdate(m[3], MONTHS[m[1].lower()], m[2])
    m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+),?\s+(\d{4})", s)
    if m and m[2].lower() in MONTHS:
        return mkdate(m[3], MONTHS[m[2].lower()], m[1])
    return None


def parse_amount(s):
    """Return (Decimal or None, currency-from-symbol or None)."""
    sym = None
    for ch in s:
        if ch in SYMBOLS:
            sym = sym or SYMBOLS[ch]
    t = re.sub(r"[$€£\s]", "", s)
    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg = True
        t = t[1:-1]
    if t.startswith("-"):
        neg = not neg
        t = t[1:]
    elif t.startswith("+"):
        t = t[1:]
    if not t or not re.fullmatch(r"[\d.,]+", t) or not re.search(r"\d", t):
        return None, sym
    if "." in t and "," in t:
        dec = "." if t.rfind(".") > t.rfind(",") else ","
        thou = "," if dec == "." else "."
        if t.count(dec) != 1:
            return None, sym
        t = t.replace(thou, "").replace(dec, ".")
    elif "," in t:
        if re.fullmatch(r"\d*,\d\d", t) and t.count(",") == 1:
            t = t.replace(",", ".")
        else:
            t = t.replace(",", "")
    elif t.count(".") > 1:
        return None, sym
    try:
        d = Decimal(t)
    except InvalidOperation:
        return None, sym
    d = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if neg:
        d = -d
    if d == 0:
        d = abs(d)
    return d, sym


def parse_ts(s):
    s = s.strip()
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})Z?", s)
    if not m:
        return datetime.min
    try:
        return datetime.strptime(m[1] + "T" + m[2], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return datetime.min


def lines(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        for line in f:
            if line.strip() == "" or line[0] == "#":
                continue
            yield line


def main(inp, out):
    rows = csv.reader(lines(inp))
    header = None
    best = {}
    for n, row in enumerate(rows):
        if header is None:
            header = {}
            for i, h in enumerate(row):
                header.setdefault(re.sub(" ", "_", h.strip().lower()), i)
            continue

        def get(name):
            i = header.get(name)
            return row[i].strip() if i is not None and i < len(row) else ""

        oid = get("order_id").upper()
        if not oid:
            continue
        amount, sym = parse_amount(get("amount"))
        if amount is None:
            continue
        odate = parse_date(get("order_date"))
        if odate is None:
            continue
        email = get("customer_email").lower()
        parts = email.split("@")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            email = ""
        cur = get("currency").upper()
        cur = SYMBOLS.get(cur, cur)
        if not cur:
            cur = sym or "USD"
        status = get("status").lower()
        if status == "canceled":
            status = "cancelled"
        if status not in STATUSES:
            status = "unknown"
        ts = parse_ts(get("updated_at"))
        rec = (oid, email, format(amount, "f"), cur, odate, status)
        if oid not in best or ts >= best[oid][0]:
            best[oid] = (ts, rec)
    result = sorted((r for _, r in best.values()), key=lambda r: (r[4], r[0]))
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["order_id", "customer_email", "amount", "currency", "order_date", "status"])
        w.writerows(result)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
