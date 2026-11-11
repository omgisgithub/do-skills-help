import csv, re, sys, datetime
from decimal import Decimal, ROUND_HALF_UP

FIELDS = ["order_id", "customer_email", "amount", "currency", "order_date", "status"]
SYM = {"$": "USD", "€": "EUR", "£": "GBP"}
MONTHS = {m: i + 1 for i, m in enumerate(
    "january february march april may june july august september october november december".split())}
for _k in list(MONTHS):
    MONTHS[_k[:3]] = MONTHS[_k]
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}


def mkdate(y, m, d):
    try:
        return datetime.date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def parse_date(s):
    m = re.fullmatch(r"(\d{4})([-/])(\d{1,2})\2(\d{1,2})", s)
    if m:
        return mkdate(m.group(1), m.group(3), m.group(4))
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        return mkdate(m.group(3), m.group(2), m.group(1))
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return mkdate(m.group(3), m.group(1), m.group(2))
    m = re.fullmatch(r"([A-Za-z]+) (\d{1,2}), (\d{4})", s)
    if m and m.group(1).lower() in MONTHS:
        return mkdate(m.group(3), MONTHS[m.group(1).lower()], m.group(2))
    m = re.fullmatch(r"(\d{1,2}) ([A-Za-z]+) (\d{4})", s)
    if m and m.group(2).lower() in MONTHS:
        return mkdate(m.group(3), MONTHS[m.group(2).lower()], m.group(1))
    return None


def parse_amount(s):
    """Return (Decimal or None, symbol currency or None)."""
    cur = None
    for ch in s:
        if ch in SYM:
            cur = SYM[ch]
            break
    t = re.sub(r"[$€£\s]", "", s)
    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg = True
        t = t[1:-1]
    if not re.fullmatch(r"[\d.,]+", t) or not re.search(r"\d", t):
        return None, cur
    if "." in t and "," in t:
        dec = "." if t.rfind(".") > t.rfind(",") else ","
        thou = "," if dec == "." else "."
        if t.count(dec) != 1:
            return None, cur
        t = t.replace(thou, "").replace(dec, ".")
    elif "," in t:
        if re.fullmatch(r".*,\d{2}", t):
            if t.count(",") != 1:
                t = t[:-3].replace(",", "") + "." + t[-2:]
            else:
                t = t.replace(",", ".")
        else:
            t = t.replace(",", "")
    else:
        if t.count(".") > 1:
            return None, cur
    try:
        v = Decimal(t)
    except Exception:
        return None, cur
    v = v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if neg:
        v = -v
    if v == 0:
        v = Decimal("0.00")
    return v, cur


def parse_updated(s):
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})Z?", s)
    if not m:
        return ""
    try:
        return datetime.datetime(*map(int, m.groups())).isoformat()
    except ValueError:
        return ""


def main(inp, out):
    with open(inp, encoding="utf-8-sig", newline="") as f:
        lines = [l for l in f.read().splitlines() if l.strip() != "" and not l.startswith("#")]
    rows = list(csv.reader(lines))
    best = {}
    if rows:
        hdr = [re.sub(" ", "_", h.strip().lower()) for h in rows[0]]
        idx = {}
        for i, h in enumerate(hdr):
            idx.setdefault(h, i)
        for pos, r in enumerate(rows[1:]):
            def g(name):
                i = idx.get(name)
                return r[i].strip() if i is not None and i < len(r) else ""
            oid = g("order_id").upper()
            if not oid:
                continue
            email = g("customer_email").lower()
            parts = email.split("@")
            if not (len(parts) == 2 and parts[0] and parts[1]):
                email = ""
            amt, sym = parse_amount(g("amount"))
            if amt is None:
                continue
            cur = g("currency").upper()
            cur = SYM.get(cur, cur) if cur else (sym or "USD")
            date = parse_date(g("order_date"))
            if not date:
                continue
            st = g("status").lower()
            if st == "canceled":
                st = "cancelled"
            if st not in STATUSES:
                st = "unknown"
            key = (parse_updated(g("updated_at")), pos)
            if oid not in best or key >= best[oid][0]:
                best[oid] = (key, [oid, email, "%.2f" % amt, cur, date, st])
    out_rows = sorted((v[1] for v in best.values()), key=lambda x: (x[4], x[0]))
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(FIELDS)
        w.writerows(out_rows)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
