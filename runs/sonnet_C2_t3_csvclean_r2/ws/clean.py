import csv
import re
import sys
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}
MONTHS = {m: i + 1 for i, m in enumerate(
    "jan feb mar apr may jun jul aug sep oct nov dec".split())}


def parse_amount(s):
    """Return (Decimal or None, currency from symbol or '')."""
    sym = next((SYMBOLS[c] for c in s if c in SYMBOLS), "")
    s = re.sub(r"[$€£\s]", "", s)
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1]
    if s.startswith("-"):
        neg, s = not neg, s[1:]
    if "," in s and "." in s:
        dec = "," if s.rfind(",") > s.rfind(".") else "."
        thou = "." if dec == "," else ","
        s = s.replace(thou, "").replace(dec, ".")
    elif "," in s:
        if re.search(r",\d\d$", s):
            i = s.rfind(",")
            s = s[:i].replace(",", "") + "." + s[i + 1:]
        else:
            s = s.replace(",", "")
    if not re.fullmatch(r"\d+(\.\d+)?|\.\d+|\d+\.", s):
        return None, sym
    d = Decimal(s).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return (-d if neg and d else d), sym


def parse_date(s):
    s = s.strip()
    y = m = d = None
    if r := re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s):
        y, m, d = r.groups()
    elif r := re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s):
        d, m, y = r.groups()
    elif r := re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s):
        m, d, y = r.groups()
    elif r := re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", s):
        m, d, y = r.groups()
    elif r := re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+),?\s+(\d{4})", s):
        d, m, y = r.groups()
    else:
        return None
    if not m.isdigit():
        w = m.lower()
        if w not in MONTH_NAMES and w not in MONTHS:
            return None
        m = MONTHS[w[:3]]
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


MONTH_NAMES = ["january", "february", "march", "april", "may", "june", "july",
               "august", "september", "october", "november", "december"]


def parse_updated(s):
    r = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})Z?", s)
    return f"{r.group(1)}T{r.group(2)}" if r else ""


def main(src, dst):
    with open(src, encoding="utf-8-sig", newline="") as f:
        lines = [l for l in f if l.strip() and not l.startswith("#")]
    rows = csv.reader(lines)
    header = [re.sub(" ", "_", h.strip().lower()) for h in next(rows, [])]
    best = {}
    for row in rows:
        r = {h: v.strip() for h, v in zip(header, row)}
        oid = r.get("order_id", "").upper()
        if not oid:
            continue
        amt, sym = parse_amount(r.get("amount", ""))
        dt = parse_date(r.get("order_date", ""))
        if amt is None or dt is None:
            continue
        email = r.get("customer_email", "").lower()
        parts = email.split("@")
        if len(parts) != 2 or not all(parts):
            email = ""
        cur = r.get("currency", "").upper()
        cur = SYMBOLS.get(cur, cur) or sym or "USD"
        st = r.get("status", "").lower()
        st = "cancelled" if st == "canceled" else st
        upd = parse_updated(r.get("updated_at", ""))
        if oid not in best or upd >= best[oid][0]:
            best[oid] = (upd, [oid, email, f"{amt:.2f}", cur, dt,
                               st if st in STATUSES else "unknown"])
    out = sorted((v[1] for v in best.values()), key=lambda x: (x[4], x[0]))
    with open(dst, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["order_id", "customer_email", "amount", "currency", "order_date", "status"])
        w.writerows(out)


if __name__ == "__main__":
    main(*sys.argv[1:3])
