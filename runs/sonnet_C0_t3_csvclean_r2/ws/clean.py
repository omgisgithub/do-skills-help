import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
MONTHS = {}
for _i, _n in enumerate(["january", "february", "march", "april", "may", "june", "july",
                         "august", "september", "october", "november", "december"], 1):
    MONTHS[_n] = _i
    MONTHS[_n[:3]] = _i
MONTHS["sept"] = 9

OUT_COLS = ["order_id", "customer_email", "amount", "currency", "order_date", "status"]


def norm_header(h):
    return h.strip().lower().replace(" ", "_")


def parse_email(v):
    v = v.strip().lower()
    parts = v.split("@")
    if len(parts) == 2 and parts[0] and parts[1]:
        return v
    return ""


def parse_amount(v):
    """Return (Decimal or None, symbol currency or None)."""
    sym = None
    for ch in v:
        if ch in SYMBOLS:
            sym = SYMBOLS[ch]
            break
    s = v
    for ch in SYMBOLS:
        s = s.replace(ch, "")
    s = re.sub(r"\s+", "", s)
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    if s.startswith("-"):
        neg = True
        s = s[1:]
    elif s.startswith("+"):
        s = s[1:]
    if not s or not re.fullmatch(r"[0-9.,]+", s):
        return None, sym
    if "." in s and "," in s:
        if s.rfind(".") > s.rfind(","):
            s = s.replace(",", "")
        else:
            s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        last = s.rfind(",")
        if len(s) - last - 1 == 2:
            s = s[:last].replace(",", "") + "." + s[last + 1:]
        else:
            s = s.replace(",", "")
    if not re.fullmatch(r"\d*\.?\d*", s) or not re.search(r"\d", s):
        return None, sym
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None, sym
    if neg:
        d = -d
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), sym


def mkdate(y, m, d):
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def parse_date(v):
    v = v.strip()
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", v)
    if m:
        return mkdate(m.group(1), m.group(2), m.group(3))
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", v)
    if m:
        return mkdate(m.group(3), m.group(2), m.group(1))
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", v)
    if m:
        return mkdate(m.group(3), m.group(1), m.group(2))
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", v)
    if m and m.group(1).lower() in MONTHS:
        return mkdate(m.group(3), MONTHS[m.group(1).lower()], m.group(2))
    m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", v)
    if m and m.group(2).lower() in MONTHS:
        return mkdate(m.group(3), MONTHS[m.group(2).lower()], m.group(1))
    return None


def parse_updated(v):
    v = v.strip()
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})Z?", v)
    if m:
        try:
            return datetime.strptime(m.group(1) + "T" + m.group(2), "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            pass
    return datetime.min


def main(inp, outp):
    with open(inp, encoding="utf-8-sig", newline="") as f:
        lines = [l for l in f.read().splitlines(True)
                 if l.strip() and not l.startswith("#")]
    reader = csv.reader(lines)
    header = None
    best = {}
    for n, row in enumerate(reader):
        if header is None:
            header = [norm_header(h) for h in row]
            continue
        rec = {}
        for h, val in zip(header, row):
            if h not in rec:
                rec[h] = val.strip()
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
        cur = SYMBOLS.get(cur, cur)
        if not cur:
            cur = sym or "USD"
        status = g("status").lower()
        if status == "canceled":
            status = "cancelled"
        if status not in STATUSES:
            status = "unknown"
        key = (parse_updated(g("updated_at")), n)
        out = [oid, parse_email(g("customer_email")), "%s" % amount, cur, odate, status]
        if oid not in best or key >= best[oid][0]:
            best[oid] = (key, out)
    rows = sorted((v[1] for v in best.values()), key=lambda r: (r[4], r[0]))
    with open(outp, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(OUT_COLS)
        w.writerows(rows)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
