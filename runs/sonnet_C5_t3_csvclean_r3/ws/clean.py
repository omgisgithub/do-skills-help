import csv
import re
import sys
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
MONTHS = {}
for _i, _n in enumerate(["january", "february", "march", "april", "may", "june", "july",
                         "august", "september", "october", "november", "december"], 1):
    MONTHS[_n] = _i
    MONTHS[_n[:3]] = _i
MONTHS["sept"] = 9


def norm_header(h):
    return h.strip().lower().replace(" ", "_")


def parse_amount(raw):
    s = raw.strip()
    symbol = next((c for c in s if c in SYMBOLS), None)
    for c in SYMBOLS:
        s = s.replace(c, "")
    s = re.sub(r"\s+", "", s)
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    if s.startswith("-"):
        neg = not neg
        s = s[1:]
    elif s.startswith("+"):
        s = s[1:]
    if not re.fullmatch(r"[\d.,]+", s) or not re.search(r"\d", s):
        return None, symbol
    if "." in s and "," in s:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        thou = "," if dec == "." else "."
        s = s.replace(thou, "")
        if s.count(dec) != 1:
            return None, symbol
        s = s.replace(dec, ".")
    elif "," in s:
        head, tail = s.rsplit(",", 1)
        if len(tail) == 2:
            s = head.replace(",", "") + "." + tail
        else:
            s = s.replace(",", "")
    elif s.count(".") > 1:
        return None, symbol
    try:
        d = Decimal(s)
    except Exception:
        return None, symbol
    if neg:
        d = -d
    d = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if d == 0:
        d = abs(d)
    return format(d, "f"), symbol


def mkdate(y, m, d):
    try:
        return datetime(int(y), int(m), int(d)).strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_date(s):
    s = s.strip()
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        return mkdate(*m.groups())
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
    s = s.strip()
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
    rows = list(csv.reader(lines))
    header = [norm_header(h) for h in rows[0]] if rows else []
    rows = rows[1:]
    idx = {}
    for i, h in enumerate(header):
        idx.setdefault(h, i)

    def get(row, name):
        i = idx.get(name)
        return row[i].strip() if i is not None and i < len(row) else ""

    best = {}
    for n, row in enumerate(rows):
        oid = get(row, "order_id").upper()
        if not oid:
            continue
        email = get(row, "customer_email").lower()
        parts = email.split("@")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            email = ""
        amount, symbol = parse_amount(get(row, "amount"))
        if amount is None:
            continue
        cur = get(row, "currency").upper()
        cur = SYMBOLS.get(cur, cur)
        if not cur:
            cur = SYMBOLS.get(symbol, "USD")
        date = parse_date(get(row, "order_date"))
        if date is None:
            continue
        status = get(row, "status").lower()
        if status == "canceled":
            status = "cancelled"
        if status not in STATUSES:
            status = "unknown"
        key = (parse_updated(get(row, "updated_at")), n)
        if oid not in best or key >= best[oid][0]:
            best[oid] = (key, [oid, email, amount, cur, date, status])

    result = sorted((v[1] for v in best.values()), key=lambda r: (r[4], r[0]))
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["order_id", "customer_email", "amount", "currency", "order_date", "status"])
        w.writerows(result)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
