import csv
import re
import sys
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

MONTHS = {m: i + 1 for i, m in enumerate(
    "january february march april may june july august september october november december".split())}
for _m, _i in list(MONTHS.items()):
    MONTHS[_m[:3]] = _i
SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}


def norm_header(h):
    return h.strip().lower().replace(" ", "_")


def parse_email(v):
    v = v.strip().lower()
    parts = v.split("@")
    if len(parts) == 2 and parts[0] and parts[1]:
        return v
    return ""


def parse_amount(raw):
    """Return (Decimal or None, symbol currency or None)."""
    sym = None
    for ch in raw:
        if ch in SYMBOLS:
            sym = SYMBOLS[ch]
            break
    s = re.sub(r"[\s$€£]", "", raw)
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    if s.startswith("-"):
        neg = not neg
        s = s[1:]
    if not s or not re.fullmatch(r"[\d.,]+", s):
        return None, sym
    if "." in s and "," in s:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        thou = "," if dec == "." else "."
        s = s.replace(thou, "")
        if s.count(dec) != 1:
            return None, sym
        s = s.replace(dec, ".")
    elif "," in s:
        if len(s.rsplit(",", 1)[1]) == 2:
            head, tail = s.rsplit(",", 1)
            s = head.replace(",", "") + "." + tail
        else:
            s = s.replace(",", "")
    if s.count(".") > 1 or not re.search(r"\d", s):
        return None, sym
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None, sym
    if neg:
        d = -d
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), sym


def mk_date(y, m, d):
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def parse_date(v):
    v = v.strip()
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", v)
    if m:
        return mk_date(m[1], m[2], m[3])
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", v)
    if m:
        return mk_date(m[3], m[2], m[1])
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", v)
    if m:
        return mk_date(m[3], m[1], m[2])
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", v)
    if m and m[1].lower() in MONTHS:
        return mk_date(m[3], MONTHS[m[1].lower()], m[2])
    m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", v)
    if m and m[2].lower() in MONTHS:
        return mk_date(m[3], MONTHS[m[2].lower()], m[1])
    return None


def parse_updated(v):
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})Z?", v.strip())
    if not m:
        return ()
    return tuple(int(x) for x in m.groups())


def main(inp, out):
    with open(inp, encoding="utf-8-sig", newline="") as f:
        lines = [l for l in f.read().splitlines(True)
                 if l.strip() and not l.startswith("#")]
    reader = csv.reader(lines)
    try:
        header = [norm_header(h) for h in next(reader)]
    except StopIteration:
        header = []
    best = {}
    for idx, row in enumerate(reader):
        rec = {}
        for h, v in zip(header, row):
            rec.setdefault(h, v.strip())
        g = lambda k: rec.get(k, "")
        oid = g("order_id").upper()
        if not oid:
            continue
        amount, sym = parse_amount(g("amount"))
        if amount is None:
            continue
        odate = parse_date(g("order_date"))
        if odate is None:
            continue
        cur = g("currency").upper()
        cur = SYMBOLS.get(cur, cur) or sym or "USD"
        status = g("status").lower()
        if status == "canceled":
            status = "cancelled"
        if status not in STATUSES:
            status = "unknown"
        out_row = [oid, parse_email(g("customer_email")), str(amount),
                   cur, odate, status]
        key = (parse_updated(g("updated_at")), idx)
        if oid not in best or key >= best[oid][0]:
            best[oid] = (key, out_row)
    rows = sorted((r for _, r in best.values()), key=lambda r: (r[4], r[0]))
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["order_id", "customer_email", "amount", "currency", "order_date", "status"])
        w.writerows(rows)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
