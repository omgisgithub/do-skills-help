import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

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
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def parse_date(s):
    s = s.strip()
    m = re.fullmatch(r"([0-9]{4})[-/]([0-9]{1,2})[-/]([0-9]{1,2})", s)
    if m:
        return mkdate(m.group(1), m.group(2), m.group(3))
    m = re.fullmatch(r"([0-9]{1,2})\.([0-9]{1,2})\.([0-9]{4})", s)
    if m:
        return mkdate(m.group(3), m.group(2), m.group(1))
    m = re.fullmatch(r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})", s)
    if m:
        return mkdate(m.group(3), m.group(1), m.group(2))
    m = re.fullmatch(r"([A-Za-z]+)\s+([0-9]{1,2})\s*,\s*([0-9]{4})", s)
    if m and m.group(1).lower() in MONTHS:
        return mkdate(m.group(3), MONTHS[m.group(1).lower()], m.group(2))
    m = re.fullmatch(r"([0-9]{1,2})\s+([A-Za-z]+)\s+([0-9]{4})", s)
    if m and m.group(2).lower() in MONTHS:
        return mkdate(m.group(3), MONTHS[m.group(2).lower()], m.group(1))
    return None


def parse_amount(s):
    """Return (Decimal or None, symbol currency or None)."""
    sym = None
    for ch in s:
        if ch in SYMBOLS:
            sym = SYMBOLS[ch]
            break
    t = re.sub(r"\s+", "", s)
    for ch in SYMBOLS:
        t = t.replace(ch, "")
    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg = True
        t = t[1:-1]
    if t.startswith("-"):
        neg = not neg
        t = t[1:]
    if not re.fullmatch(r"[0-9.,]+", t) or not re.search(r"[0-9]", t):
        return None, sym
    if "." in t and "," in t:
        if t.rfind(".") > t.rfind(","):
            t = t.replace(",", "")
        else:
            t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        if re.search(r",[0-9]{2}$", t):
            i = t.rfind(",")
            t = t[:i].replace(",", "") + "." + t[i + 1:]
        else:
            t = t.replace(",", "")
    if t.count(".") > 1 or t.startswith(".") and len(t) == 1:
        return None, sym
    try:
        v = Decimal(t)
    except Exception:
        return None, sym
    return (-v if neg else v), sym


def fmt_amount(v):
    q = v.copy_abs().quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if v < 0 and q != 0:
        q = -q
    return format(q, "f")


def parse_ts(s):
    s = s.strip()
    m = re.fullmatch(r"([0-9]{4}-[0-9]{2}-[0-9]{2})[T ]([0-9]{2}:[0-9]{2}:[0-9]{2})Z?", s)
    if not m:
        return datetime.min
    try:
        return datetime.strptime(m.group(1) + "T" + m.group(2), "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return datetime.min


def main(inp, out):
    with open(inp, encoding="utf-8-sig", newline="") as f:
        lines = [l for l in f.read().splitlines(True)
                 if l.strip() != "" and l[0] != "#"]
    rows = csv.reader(lines)
    header = next(rows, None)
    if header is None:
        header = []
    idx = {}
    for i, h in enumerate(header):
        k = h.strip().lower().replace(" ", "_")
        idx.setdefault(k, i)

    def get(r, k):
        i = idx.get(k)
        return r[i].strip() if i is not None and i < len(r) else ""

    best = {}
    for n, r in enumerate(rows):
        oid = get(r, "order_id").upper()
        if not oid:
            continue
        amt, sym = parse_amount(get(r, "amount"))
        if amt is None:
            continue
        d = parse_date(get(r, "order_date"))
        if d is None:
            continue
        email = get(r, "customer_email").lower()
        parts = email.split("@")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            email = ""
        cur = get(r, "currency").upper()
        cur = SYMBOLS.get(cur, cur)
        if not cur:
            cur = sym or "USD"
        st = get(r, "status").lower()
        if st == "canceled":
            st = "cancelled"
        if st not in STATUSES:
            st = "unknown"
        key = (parse_ts(get(r, "updated_at")), n)
        if oid not in best or key >= best[oid][0]:
            best[oid] = (key, [oid, email, fmt_amount(amt), cur, d, st])

    result = sorted((v[1] for v in best.values()), key=lambda x: (x[4], x[0]))
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["order_id", "customer_email", "amount", "currency", "order_date", "status"])
        w.writerows(result)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
