import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

MONTHS = {m: i + 1 for i, m in enumerate(
    "january february march april may june july august september october november december".split())}
for _m, _i in list(MONTHS.items()):
    MONTHS[_m[:3]] = _i
SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
F = re.ASCII
MON = "[A-Za-z]+"


def mk(y, m, d):
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def parse_date(s):
    s = s.strip()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s, F) or re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})", s, F)
    if m:
        return mk(*m.groups())
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s, F)
    if m:
        return mk(m.group(3), m.group(2), m.group(1))
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s, F)
    if m:
        return mk(m.group(3), m.group(1), m.group(2))
    m = re.fullmatch(r"(%s) (\d{1,2}), (\d{4})" % MON, s, F)
    if m and m.group(1).lower() in MONTHS:
        return mk(m.group(3), MONTHS[m.group(1).lower()], m.group(2))
    m = re.fullmatch(r"(\d{1,2}) (%s) (\d{4})" % MON, s, F)
    if m and m.group(2).lower() in MONTHS:
        return mk(m.group(3), MONTHS[m.group(2).lower()], m.group(1))
    return None


def parse_amount(s):
    """Return (Decimal, first_symbol_or_None) or (None, sym)."""
    sym = next((c for c in s if c in SYMBOLS), None)
    t = re.sub(r"[$€£\s]", "", s)
    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg = True
        t = t[1:-1]
    if not re.fullmatch(r"[0-9.,]+", t) or not re.search(r"[0-9]", t):
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
    if not re.fullmatch(r"\d+(\.\d+)?|\.\d+", t, F):
        return None, sym
    v = Decimal(t)
    return (-v if neg else v), sym


def fmt(v):
    q = abs(v).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if v < 0 and q != 0:
        q = -q
    return "{:.2f}".format(q)


def parse_ts(s):
    m = re.fullmatch(r"(\d{4})-(\d\d)-(\d\d)[T ](\d\d):(\d\d):(\d\d)Z?", s.strip(), F)
    if not m:
        return datetime.min
    try:
        return datetime(*map(int, m.groups()))
    except ValueError:
        return datetime.min


def clean(inp, outp):
    with open(inp, encoding="utf-8-sig", newline="") as f:
        lines = [l for l in f if l.strip() and not l.startswith("#")]
    reader = csv.reader(lines)
    rows = list(reader)
    if not rows:
        header, rows = [], []
    else:
        header = [h.strip().lower().replace(" ", "_") for h in rows[0]]
        rows = rows[1:]
    idx = {}
    for i, h in enumerate(header):
        idx.setdefault(h, i)

    def get(r, name):
        i = idx.get(name)
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
        if cur in SYMBOLS:
            cur = SYMBOLS[cur]
        if not cur:
            cur = SYMBOLS.get(sym, "USD")
        st = get(r, "status").lower()
        if st == "canceled":
            st = "cancelled"
        if st not in STATUSES:
            st = "unknown"
        key = (parse_ts(get(r, "updated_at")), n)
        if oid not in best or key >= best[oid][0]:
            best[oid] = (key, [oid, email, fmt(amt), cur, d, st])
    out = sorted((v[1] for v in best.values()), key=lambda x: (x[4], x[0]))
    with open(outp, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["order_id", "customer_email", "amount", "currency", "order_date", "status"])
        w.writerows(out)


if __name__ == "__main__":
    clean(sys.argv[1], sys.argv[2])
