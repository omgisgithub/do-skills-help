import csv, re, sys
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

SYM = {"$": "USD", "€": "EUR", "£": "GBP"}
MONTHS = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
STATUSES = {"pending", "paid", "shipped", "cancelled", "refunded"}


def parse_amount(s):
    """Return (Decimal or None, symbol-currency or None)."""
    cur = next((SYM[c] for c in s if c in SYM), None)
    s = re.sub(r"[$€£\s]", "", s)
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    if s.startswith("-"):
        neg, s = True, s[1:]
    if "," in s and "." in s:
        dec, th = ("." , ",") if s.rfind(".") > s.rfind(",") else (",", ".")
        s = s.replace(th, "").replace(dec, ".")
    elif "," in s:
        if re.search(r",\d\d$", s):
            i = s.rfind(",")
            s = s[:i].replace(",", "") + "." + s[i + 1:]
        else:
            s = s.replace(",", "")
    if not re.fullmatch(r"\d+(\.\d*)?|\.\d+", s):
        return None, cur
    d = Decimal(s).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return (-d if neg and d else d), cur


def parse_date(s):
    s = s.strip()
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        y, mo, d = m.groups()
    elif (m := re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)):
        d, mo, y = m.groups()
    elif (m := re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)):
        mo, d, y = m.groups()
    elif (m := re.fullmatch(r"([A-Za-z]+) (\d{1,2}), (\d{4})", s)):
        mo, d, y = m.groups()
    elif (m := re.fullmatch(r"(\d{1,2}) ([A-Za-z]+) (\d{4})", s)):
        d, mo, y = m.groups()
    else:
        return None
    if not mo.isdigit():
        mo = MONTHS.get(mo.lower()) or FULL.get(mo.lower())
        if mo is None:
            return None
    try:
        return date(int(y), int(mo), int(d)).isoformat()
    except ValueError:
        return None


FULL = {n: i + 1 for i, n in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
        "september", "october", "november", "december"])}


def main(src, dst):
    with open(src, encoding="utf-8-sig", newline="") as f:
        lines = [l for l in f if l.strip() and l[0] != "#"]
    rows = list(csv.reader(lines))
    if not rows:
        rows = [[]]
    hdr = [re.sub(" ", "_", h.strip().lower()) for h in rows[0]]
    best = {}
    for r in rows[1:]:
        g = lambda k: r[hdr.index(k)].strip() if k in hdr and hdr.index(k) < len(r) else ""
        oid = g("order_id").upper()
        if not oid:
            continue
        amt, scur = parse_amount(g("amount"))
        dt = parse_date(g("order_date"))
        if amt is None or dt is None:
            continue
        email = g("customer_email").lower()
        a, _, b = email.partition("@")
        if not (a and b and "@" not in b):
            email = ""
        cur = g("currency").upper()
        cur = SYM.get(cur, cur) or scur or "USD"
        st = g("status").lower().replace("canceled", "cancelled")
        if st not in STATUSES:
            st = "unknown"
        u = g("updated_at")
        u = u.replace(" ", "T", 1).rstrip("Z") if re.fullmatch(
            r"\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\dZ?", u) else ""
        if oid not in best or u >= best[oid][0]:
            best[oid] = (u, [oid, email, f"{amt:.2f}", cur, dt, st])
    out = sorted((v[1] for v in best.values()), key=lambda v: (v[4], v[0]))
    with open(dst, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["order_id", "customer_email", "amount", "currency", "order_date", "status"])
        w.writerows(out)


if __name__ == "__main__":
    main(*sys.argv[1:3])
