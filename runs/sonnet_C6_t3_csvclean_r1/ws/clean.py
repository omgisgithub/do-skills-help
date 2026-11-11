import csv
import re
import sys
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
MONTHS = {}
for _i, _n in enumerate(["january", "february", "march", "april", "may", "june", "july",
                         "august", "september", "october", "november", "december"], 1):
    MONTHS[_n] = _i
    MONTHS[_n[:3]] = _i

D = r"([0-9]{1,2})"
Y = r"([0-9]{4})"
DATE_FORMS = [
    (re.compile(r"([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})", re.A), "ymd"),
    (re.compile(r"([0-9]{4})/([0-9]{1,2})/([0-9]{1,2})", re.A), "ymd"),
    (re.compile(r"([0-9]{1,2})\.([0-9]{1,2})\.([0-9]{4})", re.A), "dmy"),
    (re.compile(r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})", re.A), "mdy"),
    (re.compile(r"([A-Za-z]+) ([0-9]{1,2}), ([0-9]{4})", re.A), "Mdy"),
    (re.compile(r"([0-9]{1,2}) ([A-Za-z]+) ([0-9]{4})", re.A), "dMy"),
]
UPD = re.compile(r"([0-9]{4}-[0-9]{2}-[0-9]{2})[T ]([0-9]{2}:[0-9]{2}:[0-9]{2})Z?", re.A)
NUM = re.compile(r"[0-9]+([.,][0-9]+)*|[.,][0-9]+", re.A)


def parse_date(s):
    for rx, kind in DATE_FORMS:
        m = rx.fullmatch(s)
        if not m:
            continue
        a, b, c = m.groups()
        try:
            if kind == "ymd":
                y, mo, d = int(a), int(b), int(c)
            elif kind == "dmy":
                d, mo, y = int(a), int(b), int(c)
            elif kind == "mdy":
                mo, d, y = int(a), int(b), int(c)
            elif kind == "Mdy":
                mo, d, y = MONTHS[a.lower()], int(b), int(c)
            else:
                d, mo, y = int(a), MONTHS[b.lower()], int(c)
            return date(y, mo, d).isoformat()
        except (ValueError, KeyError):
            return None
    return None


def parse_amount(raw):
    """Return (Decimal, symbol-currency or None) or (None, None)."""
    sym = None
    for ch in raw:
        if ch in SYMBOLS:
            sym = sym or SYMBOLS[ch]
    s = "".join(ch for ch in raw if ch not in SYMBOLS and not ch.isspace())
    neg = False
    m = re.fullmatch(r"\((.*)\)", s)
    if m:
        neg, s = True, m.group(1)
    if s.startswith("-"):
        if neg:
            return None, None
        neg, s = True, s[1:]
    if not re.fullmatch(r"[0-9.,]+", s) or not re.search(r"[0-9]", s):
        return None, None
    if "." in s and "," in s:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        thou = "," if dec == "." else "."
        if s.count(dec) != 1:
            return None, None
        s = s.replace(thou, "")
        s = s.replace(dec, ".")
    elif "," in s:
        if re.search(r",[0-9]{2}$", s) and not re.search(r",[0-9]{3,}$", s):
            head, tail = s.rsplit(",", 1)
            s = head.replace(",", "") + "." + tail
        else:
            s = s.replace(",", "")
    elif s.count(".") > 1:
        return None, None
    if not re.fullmatch(r"[0-9]*\.?[0-9]*", s) or not re.search(r"[0-9]", s):
        return None, None
    val = Decimal(s).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if neg and val != 0:
        val = -val
    return val, sym


def main(inp, out):
    with open(inp, encoding="utf-8-sig", newline="") as f:
        lines = [ln for ln in f.read().splitlines()
                 if ln.strip() and not ln.startswith("#")]
    rows = list(csv.reader(lines))
    if not rows:
        header, rows = [], []
    else:
        header, rows = rows[0], rows[1:]
    idx = {}
    for i, h in enumerate(header):
        idx.setdefault(h.strip().lower().replace(" ", "_"), i)

    def get(row, name):
        i = idx.get(name)
        return row[i].strip() if i is not None and i < len(row) else ""

    best = {}
    for n, row in enumerate(rows):
        oid = get(row, "order_id").upper()
        if not oid:
            continue
        amt, sym = parse_amount(get(row, "amount"))
        if amt is None:
            continue
        od = parse_date(get(row, "order_date"))
        if od is None:
            continue
        email = get(row, "customer_email").lower()
        parts = email.split("@")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            email = ""
        cur = get(row, "currency").upper()
        cur = SYMBOLS.get(cur, cur) if cur else (sym or "USD")
        st = get(row, "status").lower()
        if st == "canceled":
            st = "cancelled"
        if st not in STATUSES:
            st = "unknown"
        m = UPD.fullmatch(get(row, "updated_at"))
        upd = m.group(1) + "T" + m.group(2) if m else ""
        rec = (upd, n, [oid, email, "%.2f" % amt, cur, od, st])
        if oid not in best or (upd, n) >= (best[oid][0], best[oid][1]):
            best[oid] = rec

    result = sorted((r[2] for r in best.values()), key=lambda r: (r[4], r[0]))
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["order_id", "customer_email", "amount", "currency", "order_date", "status"])
        w.writerows(result)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
