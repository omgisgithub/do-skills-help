import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"])}
for _k, _v in list(MONTHS.items()):
    MONTHS[_k[:3]] = _v
SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
ALLOWED = {"pending", "paid", "shipped", "cancelled", "refunded"}


def parse_amount(s):
    s = s.strip()
    sym = None
    for ch in SYMBOLS:
        if ch in s:
            sym = SYMBOLS[ch]
            s = s.replace(ch, "")
    s = s.replace(" ", "")
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    if not s:
        return None, sym
    if "." in s and "," in s:
        if s.rfind(".") > s.rfind(","):
            s = s.replace(",", "")
        else:
            s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        if re.search(r",\d\d$", s):
            head, tail = s.rsplit(",", 1)
            s = head.replace(",", "") + "." + tail
        else:
            s = s.replace(",", "")
    if not re.fullmatch(r"-?\d+(\.\d+)?|-?\.\d+", s):
        return None, sym
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None, sym
    if neg:
        d = -d
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), sym


def parse_date(s):
    s = s.strip()
    try:
        m = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
        if m and (s.count("-") == 2 or s.count("/") == 2):
            return date(int(m[1]), int(m[2]), int(m[3]))
        m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
        if m:
            return date(int(m[3]), int(m[2]), int(m[1]))
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
        if m:
            return date(int(m[3]), int(m[1]), int(m[2]))
        m = re.fullmatch(r"([A-Za-z]+) (\d{1,2}), (\d{4})", s)
        if m and m[1].lower() in MONTHS:
            return date(int(m[3]), MONTHS[m[1].lower()], int(m[2]))
        m = re.fullmatch(r"(\d{1,2}) ([A-Za-z]+) (\d{4})", s)
        if m and m[2].lower() in MONTHS:
            return date(int(m[3]), MONTHS[m[2].lower()], int(m[1]))
    except ValueError:
        return None
    return None


def parse_updated(s):
    s = s.strip()
    if not s:
        return datetime.min
    s = s[:-1] if s.endswith("Z") else s
    return datetime.strptime(s.replace(" ", "T"), "%Y-%m-%dT%H:%M:%S")


def email_ok(e):
    parts = e.split("@")
    return len(parts) == 2 and parts[0] and parts[1]


def main(inp, out):
    with open(inp, encoding="utf-8-sig", newline="") as f:
        lines = [ln for ln in f.read().splitlines() if ln.strip() and not ln.startswith("#")]
    rows = list(csv.reader(lines))
    header = [h.strip().lower().replace(" ", "_") for h in rows[0]]
    idx = {h: i for i, h in enumerate(header)}
    best = {}
    for pos, r in enumerate(rows[1:]):
        def g(k):
            i = idx[k]
            return r[i].strip() if i < len(r) else ""
        oid = g("order_id").upper()
        if not oid:
            continue
        amt, sym = parse_amount(g("amount"))
        if amt is None:
            continue
        d = parse_date(g("order_date"))
        if d is None:
            continue
        em = g("customer_email").lower()
        if not email_ok(em):
            em = ""
        cur = g("currency").upper()
        cur = SYMBOLS.get(cur, cur)
        if not cur:
            cur = sym or "USD"
        st = g("status").lower()
        st = "cancelled" if st == "canceled" else st
        if st not in ALLOWED:
            st = "unknown"
        key = (parse_updated(g("updated_at")), pos)
        rec = [oid, em, "%.2f" % amt, cur, d.isoformat(), st]
        if oid not in best or key >= best[oid][0]:
            best[oid] = (key, rec)
    recs = sorted((v[1] for v in best.values()), key=lambda x: (x[4], x[0]))
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["order_id", "customer_email", "amount", "currency", "order_date", "status"])
        w.writerows(recs)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
