import csv
import re
import sys
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

SYMS = {"$": "USD", "€": "EUR", "£": "GBP"}
MONTHS = {}
for _i, _n in enumerate(["january", "february", "march", "april", "may", "june", "july",
                         "august", "september", "october", "november", "december"], 1):
    MONTHS[_n] = _i
    MONTHS[_n[:3]] = _i
MONTHS["sept"] = 9
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}


def parse_amount(raw):
    """Return (Decimal or None, symbol-currency or None)."""
    cur = None
    for ch in raw:
        if ch in SYMS:
            cur = SYMS[ch]
            break
    s = re.sub(r"[\s$€£]", "", raw)
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    if s.startswith("-"):
        neg = not neg if False else True
        s = s[1:]
    if not s or not re.fullmatch(r"[0-9.,]+", s):
        return None, cur
    if "." in s and "," in s:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        thou = "," if dec == "." else "."
        s = s.replace(thou, "")
        if dec == ",":
            s = s.replace(",", ".")
    elif "," in s:
        last = s.rfind(",")
        if re.fullmatch(r"\d{2}", s[last + 1:]):
            s = s[:last].replace(",", "") + "." + s[last + 1:]
        else:
            s = s.replace(",", "")
    if not re.fullmatch(r"\d*\.?\d*", s) or not re.search(r"\d", s):
        return None, cur
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None, cur
    if neg:
        d = -d
    return d, cur


def fmt_amount(d):
    q = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if q == 0:
        q = abs(q)
    return "{:f}".format(q)


def mk_date(y, m, d):
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def parse_date(s):
    s = s.strip()
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        return mk_date(m.group(1), m.group(2), m.group(3))
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        return mk_date(m.group(3), m.group(2), m.group(1))
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return mk_date(m.group(3), m.group(1), m.group(2))
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", s)
    if m and m.group(1).lower() in MONTHS:
        return mk_date(m.group(3), MONTHS[m.group(1).lower()], m.group(2))
    m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)
    if m and m.group(2).lower() in MONTHS:
        return mk_date(m.group(3), MONTHS[m.group(2).lower()], m.group(1))
    return None


def parse_updated(s):
    s = s.strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})Z?", s)
    if not m:
        return ""
    return "%s-%s-%sT%s:%s:%s" % m.groups()


def main(inp, out):
    with open(inp, encoding="utf-8-sig", newline="") as f:
        lines = [l for l in f if l.strip() and not l.startswith("#")]
    reader = csv.reader(lines)
    try:
        header = next(reader)
    except StopIteration:
        header = []
    names = [re.sub(" ", "_", h.strip().lower()) for h in header]
    idx = {}
    for i, n in enumerate(names):
        idx.setdefault(n, i)

    def get(row, name):
        i = idx.get(name)
        if i is None or i >= len(row):
            return ""
        return row[i].strip()

    best = {}
    for row in reader:
        if not any(c.strip() for c in row):
            continue
        oid = get(row, "order_id").upper()
        if not oid:
            continue
        email = get(row, "customer_email").lower()
        parts = email.split("@")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            email = ""
        amt, sym = parse_amount(get(row, "amount"))
        if amt is None:
            continue
        cur = get(row, "currency").upper()
        if cur in SYMS:
            cur = SYMS[cur]
        if not cur:
            cur = sym or "USD"
        od = parse_date(get(row, "order_date"))
        if od is None:
            continue
        st = get(row, "status").lower()
        if st == "canceled":
            st = "cancelled"
        if st not in STATUSES:
            st = "unknown"
        upd = parse_updated(get(row, "updated_at"))
        rec = (upd, [oid, email, fmt_amount(amt), cur, od, st])
        if oid not in best or rec[0] >= best[oid][0]:
            best[oid] = rec

    rows = sorted((r for _, r in best.values()), key=lambda r: (r[4], r[0]))
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["order_id", "customer_email", "amount", "currency", "order_date", "status"])
        w.writerows(rows)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
