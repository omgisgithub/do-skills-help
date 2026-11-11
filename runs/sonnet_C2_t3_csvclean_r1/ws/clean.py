import csv, re, sys
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

SYM = {"$": "USD", "€": "EUR", "£": "GBP"}
MONTHS = {m: i + 1 for i, m in enumerate(
    "jan feb mar apr may jun jul aug sep oct nov dec".split())}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}


def parse_amount(s):
    sym = next((c for c in s if c in SYM), None)
    t = re.sub(r"[$€£\s]", "", s)
    neg = t.startswith("(") and t.endswith(")")
    if neg:
        t = t[1:-1]
    if t.startswith("-"):
        neg, t = True, t[1:]
    if "." in t and "," in t:
        dec = "." if t.rfind(".") > t.rfind(",") else ","
    elif "," in t:
        dec = "," if re.search(r",\d\d$", t) else None
    else:
        dec = "." if "." in t else None
    if dec:
        whole, _, frac = t.rpartition(dec)
    else:
        whole, frac = t, ""
    whole = whole.replace(",", "") if dec != "," else whole.replace(".", "").replace(",", "")
    if dec == ".":
        whole = whole.replace(",", "")
    if not (whole.isdigit() or whole == "") or not (frac == "" or frac.isdigit()) or not (whole or frac):
        return None, sym
    v = Decimal((whole or "0") + "." + (frac or "0")).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return ("-" if neg and v else "") + str(v), sym


def parse_date(s):
    s = s.strip()
    try:
        if m := re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s):
            y, mo, d = m.groups()
        elif m := re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s):
            d, mo, y = m.groups()
        elif m := re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s):
            mo, d, y = m.groups()
        elif m := re.fullmatch(r"([A-Za-z]+) (\d{1,2}), (\d{4})", s):
            mo, d, y = m.groups()
            mo = MONTHS[mo[:3].lower()] if mo.lower() in FULL else 0
        elif m := re.fullmatch(r"(\d{1,2}) ([A-Za-z]+) (\d{4})", s):
            d, mo, y = m.groups()
            mo = MONTHS[mo[:3].lower()] if mo.lower() in FULL else 0
        else:
            return None
        return date(int(y), int(mo), int(d)).isoformat()
    except (ValueError, KeyError):
        return None


FULL = set(MONTHS) | {"january", "february", "march", "april", "june", "july",
                      "august", "september", "october", "november", "december"}


def parse_ts(s):
    if re.fullmatch(r"\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d Z?".replace(" Z?", "Z?"), s):
        try:
            return datetime.strptime(s.rstrip("Z").replace("T", " "), "%Y-%m-%d %H:%M:%S").isoformat()
        except ValueError:
            pass
    return ""  # empty or malformed: oldest


def clean(src, dst):
    with open(src, encoding="utf-8-sig", newline="") as f:
        lines = [l for l in f.read().splitlines() if l.strip() and l[0] != "#"]
    rows = csv.reader(lines)
    head = [h.strip().lower().replace(" ", "_") for h in next(rows, [])]
    best = {}
    for r in rows:
        g = lambda k: r[head.index(k)].strip() if k in head and head.index(k) < len(r) else ""
        oid = g("order_id").upper()
        amount, sym = parse_amount(g("amount"))
        d = parse_date(g("order_date"))
        if not oid or amount is None or not d:
            continue
        cur = g("currency").upper()
        cur = SYM.get(cur, cur) or SYM.get(sym, "USD")
        email = g("customer_email").lower()
        a, _, b = email.partition("@")
        if not (a and b and "@" not in b):
            email = ""
        st = g("status").lower().replace("canceled", "cancelled")
        if st not in STATUSES:
            st = "unknown"
        ts = parse_ts(g("updated_at"))
        if oid not in best or ts >= best[oid][0]:
            best[oid] = (ts, [oid, email, amount, cur, d, st])
    with open(dst, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["order_id", "customer_email", "amount", "currency", "order_date", "status"])
        w.writerows(sorted((v[1] for v in best.values()), key=lambda x: (x[4], x[0])))


if __name__ == "__main__":
    clean(sys.argv[1], sys.argv[2])
