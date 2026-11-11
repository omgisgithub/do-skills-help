import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

COLUMNS = ["order_id", "customer_email", "amount", "currency", "order_date", "status"]
SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
MONTHS = {}
for _i, _n in enumerate(["january", "february", "march", "april", "may", "june", "july",
                         "august", "september", "october", "november", "december"], 1):
    MONTHS[_n] = _i
    MONTHS[_n[:3]] = _i
MONTHS["sept"] = 9

OLDEST = datetime.min


def norm_header(h):
    return h.strip().lower().replace(" ", "_")


def parse_amount(raw):
    """Return (Decimal or None, symbol currency or '')."""
    s = raw.strip()
    cur = ""
    for ch in s:
        if ch in SYMBOLS:
            cur = cur or SYMBOLS[ch]
    for ch in SYMBOLS:
        s = s.replace(ch, "")
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
    if not s or not re.fullmatch(r"[0-9.,]+", s):
        return None, cur
    if "." in s and "," in s:
        if s.rfind(".") > s.rfind(","):
            dec, thou = ".", ","
        else:
            dec, thou = ",", "."
        s = s.replace(thou, "")
        if s.count(dec) != 1:
            return None, cur
        s = s.replace(dec, ".")
    elif "," in s:
        last = s.rfind(",")
        if len(s) - last - 1 == 2:
            s = s[:last].replace(",", "") + "." + s[last + 1:]
        else:
            s = s.replace(",", "")
    elif s.count(".") > 1:
        return None, cur
    if not re.search(r"[0-9]", s):
        return None, cur
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None, cur
    d = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if neg:
        d = -d
    return d, cur


def mk_date(y, m, d):
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def parse_date(raw):
    s = raw.strip()
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        return mk_date(m.group(1), m.group(2), m.group(3))
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        return mk_date(m.group(3), m.group(2), m.group(1))
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return mk_date(m.group(3), m.group(1), m.group(2))
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", s)
    if m and m.group(1).lower() in MONTHS:
        return mk_date(m.group(3), MONTHS[m.group(1).lower()], m.group(2))
    m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)
    if m and m.group(2).lower() in MONTHS:
        return mk_date(m.group(3), MONTHS[m.group(2).lower()], m.group(1))
    return None


def parse_updated(raw):
    s = raw.strip()
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})Z?", s)
    if not m:
        return OLDEST
    try:
        return datetime.strptime(m.group(1) + "T" + m.group(2), "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return OLDEST


def clean_email(raw):
    e = raw.strip().lower()
    if e.count("@") != 1:
        return ""
    left, right = e.split("@")
    return e if left and right else ""


def main(inp, out):
    with open(inp, newline="", encoding="utf-8-sig") as f:
        lines = [l for l in f.read().splitlines(True)
                 if l.strip() and not l.startswith("#")]
    reader = csv.reader(lines)
    rows = list(reader)
    best = {}
    if rows:
        header = [norm_header(h) for h in rows[0]]
        idx = {}
        for i, h in enumerate(header):
            idx.setdefault(h, i)

        def get(row, name):
            i = idx.get(name)
            return row[i].strip() if i is not None and i < len(row) else ""

        for n, row in enumerate(rows[1:]):
            oid = get(row, "order_id").upper()
            if not oid:
                continue
            amt, sym = parse_amount(get(row, "amount"))
            if amt is None:
                continue
            od = parse_date(get(row, "order_date"))
            if od is None:
                continue
            cur = get(row, "currency").upper()
            cur = SYMBOLS.get(cur, cur) or sym or "USD"
            status = get(row, "status").lower()
            if status == "canceled":
                status = "cancelled"
            if status not in STATUSES:
                status = "unknown"
            amt_s = "0.00" if amt == 0 else format(amt, "f")
            rec = [oid, clean_email(get(row, "customer_email")), amt_s, cur, od, status]
            key = (parse_updated(get(row, "updated_at")), n)
            if oid not in best or key >= best[oid][0]:
                best[oid] = (key, rec)
    result = sorted((v[1] for v in best.values()), key=lambda r: (r[4], r[0]))
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLUMNS)
        w.writerows(result)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: clean.py INPUT.csv OUTPUT.csv")
    main(sys.argv[1], sys.argv[2])
