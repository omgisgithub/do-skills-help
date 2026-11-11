import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
MONTHS = {m: i + 1 for i, m in enumerate(
    "jan feb mar apr may jun jul aug sep oct nov dec".split())}
FULL = ("january february march april may june july august september "
        "october november december").split()
MONTH_NAMES = {}
for _i, _f in enumerate(FULL):
    MONTH_NAMES[_f] = _i + 1
    MONTH_NAMES[_f[:3]] = _i + 1

D = "[0-9]"
RE_YMD = re.compile(r"(%s{4})[-/](%s{1,2})[-/](%s{1,2})" % (D, D, D))
RE_ISO = re.compile(r"(%s{4})-(%s{1,2})-(%s{1,2})" % (D, D, D))
RE_SLASH_YMD = re.compile(r"(%s{4})/(%s{1,2})/(%s{1,2})" % (D, D, D))
RE_DMY = re.compile(r"(%s{1,2})\.(%s{1,2})\.(%s{4})" % (D, D, D))
RE_MDY = re.compile(r"(%s{1,2})/(%s{1,2})/(%s{4})" % (D, D, D))
RE_MON_D = re.compile(r"([A-Za-z]+) (%s{1,2}), (%s{4})" % (D, D))
RE_D_MON = re.compile(r"(%s{1,2}) ([A-Za-z]+) (%s{4})" % (D, D))
RE_UPD = re.compile(r"%s{4}-%s{2}-%s{2}[T ]%s{2}:%s{2}:%s{2}Z?" % ((D,) * 6))


def mk(y, m, d):
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def parse_date(s):
    m = RE_ISO.fullmatch(s) or RE_SLASH_YMD.fullmatch(s)
    if m:
        return mk(m[1], m[2], m[3])
    m = RE_DMY.fullmatch(s)
    if m:
        return mk(m[3], m[2], m[1])
    m = RE_MDY.fullmatch(s)
    if m:
        return mk(m[3], m[1], m[2])
    m = RE_MON_D.fullmatch(s)
    if m and m[1].lower() in MONTH_NAMES:
        return mk(m[3], MONTH_NAMES[m[1].lower()], m[2])
    m = RE_D_MON.fullmatch(s)
    if m and m[2].lower() in MONTH_NAMES:
        return mk(m[3], MONTH_NAMES[m[2].lower()], m[1])
    return None


def parse_amount(s):
    """Return (Decimal, symbol_currency_or_None) or (None, None)."""
    sym = None
    for ch in s:
        if ch in SYMBOLS:
            sym = SYMBOLS[ch]
            break
    t = "".join(ch for ch in s if ch not in SYMBOLS and not ch.isspace())
    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg = True
        t = t[1:-1]
    if not re.fullmatch(r"[0-9.,]+", t):
        return None, sym
    if "." in t and "," in t:
        dec = "." if t.rfind(".") > t.rfind(",") else ","
        thou = "," if dec == "." else "."
        head, _, tail = t.rpartition(dec)
        head = head.replace(thou, "")
        if dec in head:
            return None, sym
        t = head + "." + tail
    elif "," in t:
        head, _, tail = t.rpartition(",")
        if len(tail) == 2 and tail.isdigit():
            t = head.replace(",", "") + "." + tail
        else:
            t = t.replace(",", "")
    elif t.count(".") > 1:
        return None, sym
    if not re.search("[0-9]", t) or not re.fullmatch(r"[0-9]*\.?[0-9]*", t):
        return None, sym
    v = Decimal(t).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if neg:
        v = -v
    if v == 0:
        v = Decimal("0.00")
    return v, sym


def parse_updated(s):
    if not RE_UPD.fullmatch(s):
        return ""
    t = s.rstrip("Z").replace(" ", "T")
    try:
        datetime.strptime(t, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return ""
    return t


def clean_email(s):
    s = s.strip().lower()
    if s.count("@") == 1:
        a, b = s.split("@")
        if a and b:
            return s
    return ""


def main(inp, out):
    with open(inp, encoding="utf-8-sig", newline="") as f:
        lines = [l for l in f.read().splitlines(True)
                 if l.strip() and not l.startswith("#")]
    rows = list(csv.reader(lines))
    best = {}
    if rows:
        idx = {}
        for i, h in enumerate(rows[0]):
            k = h.strip().lower().replace(" ", "_")
            idx.setdefault(k, i)

        def get(r, k):
            i = idx.get(k)
            return r[i].strip() if i is not None and i < len(r) else ""

        for n, r in enumerate(rows[1:]):
            oid = get(r, "order_id").upper()
            if not oid:
                continue
            amt, sym = parse_amount(get(r, "amount"))
            if amt is None:
                continue
            dt = parse_date(get(r, "order_date"))
            if dt is None:
                continue
            cur = get(r, "currency").upper()
            cur = SYMBOLS.get(cur, cur)
            if not cur:
                cur = sym or "USD"
            st = get(r, "status").lower()
            if st == "canceled":
                st = "cancelled"
            if st not in STATUSES:
                st = "unknown"
            rec = (oid, clean_email(get(r, "customer_email")),
                   format(amt, "f"), cur, dt, st)
            key = (parse_updated(get(r, "updated_at")), n)
            if oid not in best or key > best[oid][0]:
                best[oid] = (key, rec)
    result = sorted((v[1] for v in best.values()), key=lambda x: (x[4], x[0]))
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["order_id", "customer_email", "amount", "currency",
                    "order_date", "status"])
        w.writerows(result)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
