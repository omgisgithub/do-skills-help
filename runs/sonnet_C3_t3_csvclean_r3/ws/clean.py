import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
MONTHS = {}
for _i, _n in enumerate(["january", "february", "march", "april", "may", "june", "july",
                         "august", "september", "october", "november", "december"], 1):
    MONTHS[_n] = _i
    MONTHS[_n[:3]] = _i
MONTHS["sept"] = 9


def mkdate(y, m, d):
    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def parse_date(s):
    s = s.strip()
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        return mkdate(m.group(1), m.group(2), m.group(3))
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        return mkdate(m.group(3), m.group(2), m.group(1))
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return mkdate(m.group(3), m.group(1), m.group(2))
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", s)
    if m and m.group(1).lower() in MONTHS:
        return mkdate(m.group(3), MONTHS[m.group(1).lower()], m.group(2))
    m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+),?\s+(\d{4})", s)
    if m and m.group(2).lower() in MONTHS:
        return mkdate(m.group(3), MONTHS[m.group(2).lower()], m.group(1))
    return None


def parse_amount(s):
    """Return (Decimal or None, symbol currency or '')."""
    sym = ""
    for ch in s:
        if ch in SYMBOLS:
            sym = SYMBOLS[ch]
            break
    t = re.sub(r"[\s$€£]", "", s)
    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg = True
        t = t[1:-1]
    if t.startswith("-"):
        neg = not neg
        t = t[1:]
    elif t.startswith("+"):
        t = t[1:]
    if not t or not re.fullmatch(r"[0-9.,]+", t):
        return None, sym
    if "." in t and "," in t:
        dec = "." if t.rfind(".") > t.rfind(",") else ","
        other = "," if dec == "." else "."
        if t.count(dec) != 1:
            return None, sym
        t = t.replace(other, "").replace(dec, ".")
    elif "," in t:
        if re.fullmatch(r"\d*,\d\d", t.rsplit(",", 1)[0] + "," + t.rsplit(",", 1)[1]) and \
                len(t.rsplit(",", 1)[1]) == 2 and t.count(",") == 1:
            t = t.replace(",", ".")
        else:
            t = t.replace(",", "")
    elif t.count(".") > 1:
        return None, sym
    if not re.fullmatch(r"\d+(\.\d*)?|\.\d+", t):
        return None, sym
    try:
        v = Decimal(t)
    except InvalidOperation:
        return None, sym
    return (-v if neg else v), sym


def parse_updated(s):
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})Z?", s.strip())
    if m:
        try:
            return datetime.strptime(m.group(1) + "T" + m.group(2), "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            pass
    return datetime.min


def main(inp, outp):
    with open(inp, encoding="utf-8-sig", newline="") as f:
        lines = [l for l in f.read().splitlines() if l.strip() and l[0] != "#"]
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
        return row[i].strip() if i is not None and i < len(row) else ""

    best = {}
    for n, row in enumerate(reader):
        oid = get(row, "order_id").upper()
        if not oid:
            continue
        amt, sym = parse_amount(get(row, "amount"))
        if amt is None:
            continue
        d = parse_date(get(row, "order_date"))
        if d is None:
            continue
        amt = amt.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if amt == 0:
            amt = Decimal("0.00")
        email = get(row, "customer_email").lower()
        parts = email.split("@")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            email = ""
        cur = get(row, "currency").upper()
        cur = SYMBOLS.get(cur, cur)
        if not cur:
            cur = sym or "USD"
        status = get(row, "status").lower()
        if status == "canceled":
            status = "cancelled"
        if status not in STATUSES:
            status = "unknown"
        key = parse_updated(get(row, "updated_at"))
        out = (oid, email, "%.2f" % amt, cur, d.isoformat(), status)
        if oid not in best or key >= best[oid][0]:
            best[oid] = (key, out)

    rows = sorted((v[1] for v in best.values()), key=lambda r: (r[4], r[0]))
    with open(outp, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["order_id", "customer_email", "amount", "currency", "order_date", "status"])
        w.writerows(rows)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
