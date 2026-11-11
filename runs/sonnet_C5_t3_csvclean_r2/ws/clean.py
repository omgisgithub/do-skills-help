import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

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
    symbol = ""
    for ch in s:
        if ch in SYMBOLS:
            symbol = ch
            break
    for ch in SYMBOLS:
        s = s.replace(ch, "")
    s = re.sub(r"\s+", "", s)
    if not s:
        return None, symbol
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
        return None, symbol
    if "." in s and "," in s:
        if s.rfind(".") > s.rfind(","):
            s = s.replace(",", "")
        else:
            s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        if re.fullmatch(r"\d{2}", s.rsplit(",", 1)[1]):
            head, tail = s.rsplit(",", 1)
            s = head.replace(",", "") + "." + tail
        else:
            s = s.replace(",", "")
    if s.count(".") > 1 or not re.search(r"\d", s):
        return None, symbol
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None, symbol
    if neg:
        d = -d
    q = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)  # half away from zero
    if q == 0:
        q = abs(q)
    return format(q, "f"), symbol


def mkdate(y, m, d):
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def parse_date(raw):
    s = raw.strip()
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


def parse_updated(raw):
    s = raw.strip()
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})Z?", s)
    if not m:
        return datetime.min
    try:
        return datetime.strptime(m.group(1) + "T" + m.group(2), "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return datetime.min


def clean_email(raw):
    e = raw.strip().lower()
    if e.count("@") != 1:
        return ""
    a, b = e.split("@")
    return e if a and b else ""


def main(src, dst):
    with open(src, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
        text = f.read()
    text = text.lstrip("﻿")
    lines = [ln for ln in text.splitlines(True) if ln.strip() and not ln.startswith("#")]
    reader = csv.reader(lines)
    header = None
    best = {}
    for n, row in enumerate(reader):
        if header is None:
            header = {}
            for i, h in enumerate(row):
                header.setdefault(norm_header(h), i)
            continue
        if not any(c.strip() for c in row):
            continue

        def get(name):
            i = header.get(name)
            return row[i].strip() if i is not None and i < len(row) else ""

        oid = get("order_id").upper()
        if not oid:
            continue
        amount, symbol = parse_amount(get("amount"))
        if amount is None:
            continue
        od = parse_date(get("order_date"))
        if od is None:
            continue
        cur = get("currency").upper()
        if cur in SYMBOLS:
            cur = SYMBOLS[cur]
        if not cur:
            cur = SYMBOLS.get(symbol, "USD")
        status = get("status").lower()
        if status == "canceled":
            status = "cancelled"
        if status not in STATUSES:
            status = "unknown"
        key = parse_updated(get("updated_at"))
        out = [oid, clean_email(get("customer_email")), amount, cur, od, status]
        if oid not in best or key >= best[oid][0]:
            best[oid] = (key, out)
    rows = sorted((v[1] for v in best.values()), key=lambda r: (r[4], r[0]))
    with open(dst, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["order_id", "customer_email", "amount", "currency", "order_date", "status"])
        w.writerows(rows)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
