import csv
import re
import sys
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

MONTHS = {}
for _i, _n in enumerate(["january", "february", "march", "april", "may", "june", "july",
                         "august", "september", "october", "november", "december"], 1):
    MONTHS[_n] = _i
    MONTHS[_n[:3]] = _i
SYMS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}


def parse_amount(raw):
    """Return (Decimal or None, symbol currency or None)."""
    s = raw.strip()
    cur = None
    for ch in s:
        if ch in SYMS:
            cur = SYMS[ch]
            break
    s = re.sub(r"[$€£\s]", "", s)
    neg = False
    m = re.fullmatch(r"\((.*)\)", s)
    if m:
        neg, s = True, m.group(1)
    if not s or not re.fullmatch(r"[0-9.,]+", s):
        return None, cur
    if "." in s and "," in s:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        thou = "," if dec == "." else "."
        ip, _, fp = s.rpartition(dec)
        ip = ip.replace(thou, "")
        if dec in ip or not fp.isdigit() and fp:
            return None, cur
    elif "," in s:
        ip, _, fp = s.rpartition(",")
        if len(fp) == 2 and fp.isdigit():
            ip = ip.replace(",", "")
        else:
            ip, fp = s.replace(",", ""), ""
    elif "." in s:
        if s.count(".") > 1:
            return None, cur
        ip, _, fp = s.partition(".")
    else:
        ip, fp = s, ""
    if not (ip + fp).isdigit() or (ip + fp) == "" or not (ip or fp):
        return None, cur
    try:
        d = Decimal((ip or "0") + "." + (fp or "0"))
    except Exception:
        return None, cur
    d = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if neg:
        d = -d
    return d, cur


def mkdate(y, m, d):
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def parse_date(s):
    s = s.strip()
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m and (s[4] == s[m.start(2) - 1 + 0] or True):
        sep1, sep2 = s[4], s[m.end(2)]
        if sep1 == sep2:
            return mkdate(m.group(1), m.group(2), m.group(3))
        return None
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


def parse_updated(s):
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})Z?", s.strip())
    return m.group(1) + "T" + m.group(2) if m else ""


def valid_email(e):
    p = e.split("@")
    return len(p) == 2 and p[0] != "" and p[1] != ""


def clean(inp, out):
    with open(inp, encoding="utf-8-sig", newline="") as f:
        lines = [l for l in f.read().splitlines() if l.strip() != "" and not l.startswith("#")]
    rows = list(csv.reader(lines))
    best = {}
    if rows:
        hdr = [h.strip().lower().replace(" ", "_") for h in rows[0]]
        idx = {}
        for i, h in enumerate(hdr):
            idx.setdefault(h, i)
        for seq, r in enumerate(rows[1:]):
            def g(k):
                i = idx.get(k)
                return r[i].strip() if i is not None and i < len(r) else ""
            oid = g("order_id").upper()
            if not oid:
                continue
            amt, sym = parse_amount(g("amount"))
            if amt is None:
                continue
            od = parse_date(g("order_date"))
            if od is None:
                continue
            cur = g("currency").upper()
            cur = SYMS.get(cur, cur)
            if not cur:
                cur = sym or "USD"
            email = g("customer_email").lower()
            if not valid_email(email):
                email = ""
            st = g("status").lower()
            if st == "canceled":
                st = "cancelled"
            if st not in STATUSES:
                st = "unknown"
            astr = "0.00" if amt == 0 else format(amt, "f")
            key = (parse_updated(g("updated_at")), seq)
            rec = (oid, email, astr, cur, od, st)
            if oid not in best or key >= best[oid][0]:
                best[oid] = (key, rec)
    recs = sorted((v[1] for v in best.values()), key=lambda r: (r[4], r[0]))
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["order_id", "customer_email", "amount", "currency", "order_date", "status"])
        w.writerows(recs)


if __name__ == "__main__":
    clean(sys.argv[1], sys.argv[2])
