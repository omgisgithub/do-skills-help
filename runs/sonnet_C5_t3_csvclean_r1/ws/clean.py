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


def parse_amount(raw):
    """Return (Decimal, symbol_currency_or_None) or (None, symbol)."""
    symbol = None
    for ch in raw:
        if ch in SYMBOLS:
            symbol = SYMBOLS[ch]
            break
    s = re.sub(r"[$€£\s]", "", raw)
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    if s.startswith("-"):
        neg = not neg
        s = s[1:]
    if not s or not re.fullmatch(r"[0-9.,]+", s) or not re.search(r"[0-9]", s):
        return None, symbol
    has_dot, has_comma = "." in s, "," in s
    if has_dot and has_comma:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
    elif has_comma:
        dec = "," if re.search(r",\d\d$", s) else None
    elif has_dot:
        dec = "."
    else:
        dec = None
    if dec:
        head, _, tail = s.rpartition(dec)
        other = "," if dec == "." else "."
        if dec in head or not re.fullmatch(r"[0-9]*", tail):
            return None, symbol
        head = head.replace(other, "")
        if not head and not tail:
            return None, symbol
        num = (head or "0") + "." + (tail or "0")
    else:
        num = s.replace(",", "").replace(".", "")
    try:
        d = Decimal(num)
    except Exception:
        return None, symbol
    d = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)  # half away from zero (sign applied after)
    if neg:
        d = -d
    return d, symbol


def mkdate(y, m, d):
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def parse_date(s):
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        return mkdate(m.group(1), m.group(2), m.group(3))
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        return mkdate(m.group(3), m.group(2), m.group(1))
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return mkdate(m.group(3), m.group(1), m.group(2))
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", s)
    if m and m.group(1).lower() in MONTHS:
        return mkdate(m.group(3), MONTHS[m.group(1).lower()], m.group(2))
    m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)
    if m and m.group(2).lower() in MONTHS:
        return mkdate(m.group(3), MONTHS[m.group(2).lower()], m.group(1))
    return None


def parse_updated(s):
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})Z?", s)
    if m:
        try:
            return datetime.strptime(m.group(1) + "T" + m.group(2), "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            pass
    return datetime.min


def main(inp, out):
    with open(inp, encoding="utf-8-sig", newline="") as f:
        lines = [l for l in f.read().splitlines(True)
                 if l.strip() and not l.startswith("#")]
    reader = csv.reader(lines)
    try:
        header = next(reader)
    except StopIteration:
        header = []
    names = [h.strip().lower().replace(" ", "_") for h in header]
    idx = {}
    for i, n in enumerate(names):
        idx.setdefault(n, i)

    best = {}
    for n, row in enumerate(reader):
        if not any(c.strip() for c in row):
            continue

        def get(name):
            i = idx.get(name)
            return row[i].strip() if i is not None and i < len(row) else ""

        oid = get("order_id").upper()
        if not oid:
            continue
        amount, sym = parse_amount(get("amount"))
        if amount is None:
            continue
        od = parse_date(get("order_date"))
        if od is None:
            continue
        email = get("customer_email").lower()
        parts = email.split("@")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            email = ""
        cur = get("currency").upper()
        cur = SYMBOLS.get(cur, cur)
        if not cur:
            cur = sym or "USD"
        status = get("status").lower()
        if status == "canceled":
            status = "cancelled"
        if status not in STATUSES:
            status = "unknown"
        key = (parse_updated(get("updated_at")), n)
        rec = (oid, email, format(amount, "f"), cur, od, status)
        if oid not in best or key >= best[oid][0]:
            best[oid] = (key, rec)

    rows = sorted((v[1] for v in best.values()), key=lambda r: (r[4], r[0]))
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["order_id", "customer_email", "amount", "currency", "order_date", "status"])
        w.writerows(rows)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
