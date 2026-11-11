import csv
import re
import sys
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
MONTHS = {m: i + 1 for i, m in enumerate(
    "january february march april may june july august september october november december".split())}
for _m, _i in list(MONTHS.items()):
    MONTHS[_m[:3]] = _i
UPDATED_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}Z?$")


def norm_header(h):
    return h.strip().lower().replace(" ", "_")


def parse_email(v):
    v = v.strip().lower()
    parts = v.split("@")
    if len(parts) == 2 and parts[0] and parts[1]:
        return v
    return ""


def parse_amount(v):
    """Return (Decimal or None, currency-from-symbol or None)."""
    s = v.strip()
    sym = None
    for ch in s:
        if ch in SYMBOLS:
            sym = SYMBOLS[ch]
            break
    for ch in SYMBOLS:
        s = s.replace(ch, "")
    s = re.sub(r"\s+", "", s)
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    if s.startswith("-"):
        neg = not neg
        s = s[1:]
    if not s or not re.fullmatch(r"[0-9.,]+", s):
        return None, sym
    if "." in s and "," in s:
        if s.rfind(".") > s.rfind(","):
            s = s.replace(",", "")
        else:
            s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        if re.search(r",\d{2}$", s):
            head, tail = s.rsplit(",", 1)
            s = head.replace(",", "") + "." + tail
        else:
            s = s.replace(",", "")
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None, sym
    if not d.is_finite():
        return None, sym
    if neg:
        d = -d
    return d, sym


def format_amount(d):
    q = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)  # half away from zero
    if q == 0:
        q = abs(q)
    return "{:f}".format(q)


def mk_date(y, m, d):
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def parse_date(v):
    s = v.strip()
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        return mk_date(int(m[1]), int(m[2]), int(m[3]))
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        return mk_date(int(m[3]), int(m[2]), int(m[1]))
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return mk_date(int(m[3]), int(m[1]), int(m[2]))
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", s)
    if m and m[1].lower() in MONTHS:
        return mk_date(int(m[3]), MONTHS[m[1].lower()], int(m[2]))
    m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)
    if m and m[2].lower() in MONTHS:
        return mk_date(int(m[3]), MONTHS[m[2].lower()], int(m[1]))
    return None


def parse_updated(v):
    s = v.strip()
    if not UPDATED_RE.match(s):
        return ""
    s = s.rstrip("Z").replace(" ", "T")
    try:
        date(int(s[:4]), int(s[5:7]), int(s[8:10]))
    except ValueError:
        return ""
    return s


def main(src, dst):
    with open(src, encoding="utf-8-sig", newline="") as f:
        lines = [ln for ln in f.read().splitlines(True)
                 if ln.strip() and not ln.startswith("#")]
    reader = csv.reader(lines)
    rows = list(reader)
    best = {}
    if rows:
        header = [norm_header(h) for h in rows[0]]
        idx = {}
        for i, h in enumerate(header):
            idx.setdefault(h, i)

        def get(row, name):
            i = idx.get(name)
            return row[i].strip() if i is not None and i < len(row) else ""

        for row in rows[1:]:
            oid = get(row, "order_id").upper()
            if not oid:
                continue
            amt, sym = parse_amount(get(row, "amount"))
            if amt is None:
                continue
            od = parse_date(get(row, "order_date"))
            if od is None:
                continue
            cur = get(row, "currency").upper()
            cur = SYMBOLS.get(cur, cur) if cur else (sym or "USD")
            status = get(row, "status").lower()
            if status == "canceled":
                status = "cancelled"
            if status not in STATUSES:
                status = "unknown"
            upd = parse_updated(get(row, "updated_at"))
            rec = (oid, parse_email(get(row, "customer_email")),
                   format_amount(amt), cur, od, status)
            if oid not in best or upd >= best[oid][0]:
                best[oid] = (upd, rec)
    out = sorted((r for _, r in best.values()), key=lambda r: (r[4], r[0]))
    with open(dst, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["order_id", "customer_email", "amount", "currency", "order_date", "status"])
        w.writerows(out)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: clean.py INPUT.csv OUTPUT.csv")
    main(sys.argv[1], sys.argv[2])
