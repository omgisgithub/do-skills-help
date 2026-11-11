import csv
import re
import sys
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

MONTHS = {m: i + 1 for i, m in enumerate(
    "january february march april may june july august september october november december".split())}
for _k, _v in list(MONTHS.items()):
    MONTHS[_k[:3]] = _v
MONTHS["sept"] = 9

SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}


def mkdate(y, m, d):
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def parse_date(s):
    s = s.strip()
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        return mkdate(*m.groups())
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        return mkdate(m.group(3), m.group(2), m.group(1))
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return mkdate(m.group(3), m.group(1), m.group(2))
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", s)
    if m and m.group(1).lower() in MONTHS:
        return mkdate(m.group(3), MONTHS[m.group(1).lower()], m.group(2))
    m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)
    if m and m.group(2).lower() in MONTHS:
        return mkdate(m.group(3), MONTHS[m.group(2).lower()], m.group(1))
    return None


def parse_amount(s):
    """Return (Decimal or None, currency-from-symbol or '')."""
    sym = ""
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
    if not t:
        return None, sym
    if "." in t and "," in t:
        if t.rfind(".") > t.rfind(","):
            t = t.replace(",", "")
        else:
            t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        if re.search(r",\d\d$", t):
            i = t.rfind(",")
            t = t[:i].replace(",", "") + "." + t[i + 1:]
        else:
            t = t.replace(",", "")
    if not re.fullmatch(r"\d+(\.\d*)?|\.\d+", t):
        return None, sym
    try:
        d = Decimal(t)
    except InvalidOperation:
        return None, sym
    if neg:
        d = -d
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), sym


def parse_updated(s):
    s = s.strip()
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})Z?", s)
    if not m:
        return ""
    try:
        datetime.strptime(m.group(1) + "T" + m.group(2), "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return ""
    return m.group(1) + "T" + m.group(2)


def main(inp, out):
    with open(inp, encoding="utf-8-sig", newline="") as f:
        lines = [l for l in f.read().splitlines(True)
                 if l.strip() and not l.startswith("#")]
    reader = csv.reader(lines)
    try:
        header = next(reader)
    except StopIteration:
        header = []
    idx = {}
    for i, h in enumerate(header):
        k = h.strip().lower().replace(" ", "_")
        idx.setdefault(k, i)

    def get(row, k):
        i = idx.get(k)
        return row[i].strip() if i is not None and i < len(row) else ""

    best = {}
    for n, row in enumerate(reader):
        oid = get(row, "order_id").upper()
        if not oid:
            continue
        email = get(row, "customer_email").lower()
        if email.count("@") != 1 or not all(p.strip() for p in email.split("@")):
            email = ""
        amt, sym = parse_amount(get(row, "amount"))
        if amt is None:
            continue
        cur = get(row, "currency").upper()
        cur = SYMBOLS.get(cur, cur) or sym or "USD"
        od = parse_date(get(row, "order_date"))
        if od is None:
            continue
        st = get(row, "status").lower()
        if st == "canceled":
            st = "cancelled"
        if st not in STATUSES:
            st = "unknown"
        key = (parse_updated(get(row, "updated_at")), n)
        rec = (key, [oid, email, str(amt), cur, od, st])
        if oid not in best or key >= best[oid][0]:
            best[oid] = rec

    rows = sorted((r for _, r in best.values()), key=lambda r: (r[4], r[0]))
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["order_id", "customer_email", "amount", "currency", "order_date", "status"])
        w.writerows(rows)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: clean.py INPUT.csv OUTPUT.csv")
    main(sys.argv[1], sys.argv[2])
