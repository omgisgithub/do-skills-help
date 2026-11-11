import csv, re, sys, datetime
from decimal import Decimal, ROUND_HALF_UP

SYM = {'$': 'USD', '€': 'EUR', '£': 'GBP'}
MONTHS = {m: i + 1 for i, m in enumerate(
    'january february march april may june july august september october november december'.split())}
for _m, _i in list(MONTHS.items()):
    MONTHS[_m[:3]] = _i
STATUSES = {'pending', 'paid', 'shipped', 'cancelled', 'refunded'}
COLS = ['order_id', 'customer_email', 'amount', 'currency', 'order_date', 'status']


def parse_amount(s):
    """Return (Decimal, symbol_currency_or_None) or None."""
    s = s.strip()
    syms = [c for c in s if c in SYM]
    cur = SYM[syms[0]] if syms else None
    t = re.sub(r'[$€£\s]', '', s)
    neg = False
    if t.startswith('(') and t.endswith(')'):
        neg = True
        t = t[1:-1]
    if not re.fullmatch(r'[0-9.,]*[0-9][0-9.,]*', t):
        return None
    if '.' in t and ',' in t:
        dec = '.' if t.rfind('.') > t.rfind(',') else ','
        thou = ',' if dec == '.' else '.'
        if t.count(dec) != 1:
            return None
        ip, fp = t.split(dec)
        ip = ip.replace(thou, '')
        if not (ip + fp).isdigit():
            return None
        t = ip + '.' + fp
    elif ',' in t:
        head, last = t.rsplit(',', 1)
        if re.fullmatch(r'\d{2}', last):
            t = head.replace(',', '') + '.' + last
        else:
            t = t.replace(',', '')
    elif t.count('.') > 1:
        return None
    if t.startswith('.'):
        t = '0' + t
    if not re.fullmatch(r'\d+(\.\d*)?', t):
        return None
    v = Decimal(t)
    return (-v if neg else v), cur


def mkdate(y, m, d):
    try:
        return datetime.date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def parse_date(s):
    s = s.strip()
    m = re.fullmatch(r'(\d{4})-(\d{1,2})-(\d{1,2})', s) or re.fullmatch(r'(\d{4})/(\d{1,2})/(\d{1,2})', s)
    if m:
        return mkdate(*m.groups())
    m = re.fullmatch(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', s)
    if m:
        return mkdate(m.group(3), m.group(2), m.group(1))
    m = re.fullmatch(r'(\d{1,2})/(\d{1,2})/(\d{4})', s)
    if m:
        return mkdate(m.group(3), m.group(1), m.group(2))
    m = re.fullmatch(r'([A-Za-z]+) (\d{1,2}), (\d{4})', s)
    if m and m.group(1).lower() in MONTHS:
        return mkdate(m.group(3), MONTHS[m.group(1).lower()], m.group(2))
    m = re.fullmatch(r'(\d{1,2}) ([A-Za-z]+) (\d{4})', s)
    if m and m.group(2).lower() in MONTHS:
        return mkdate(m.group(3), MONTHS[m.group(2).lower()], m.group(1))
    return None


def parse_updated(s):
    s = s.strip()
    m = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})Z?', s)
    if not m:
        return datetime.datetime.min
    try:
        return datetime.datetime(*map(int, m.groups()))
    except ValueError:
        return datetime.datetime.min


def clean_email(s):
    s = s.strip().lower()
    if s.count('@') != 1:
        return ''
    a, b = s.split('@')
    return s if a and b else ''


def main(inp, out):
    with open(inp, newline='', encoding='utf-8-sig') as f:
        lines = [l for l in f.read().splitlines(True)
                 if l.strip() != '' and not l.startswith('#')]
    rows = list(csv.reader(lines))
    best = {}
    if rows:
        hdr = [h.strip().lower().replace(' ', '_') for h in rows[0]]
        idx = {}
        for i, h in enumerate(hdr):
            idx.setdefault(h, i)
        for n, r in enumerate(rows[1:]):
            def g(c):
                i = idx.get(c)
                return r[i].strip() if i is not None and i < len(r) else ''
            oid = g('order_id').upper()
            if not oid:
                continue
            a = parse_amount(g('amount'))
            if a is None:
                continue
            val, scur = a
            date = parse_date(g('order_date'))
            if date is None:
                continue
            cur = g('currency').upper()
            cur = SYM.get(cur, cur)
            if not cur:
                cur = scur or 'USD'
            st = g('status').lower()
            if st == 'canceled':
                st = 'cancelled'
            if st not in STATUSES:
                st = 'unknown'
            amt = str(val.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
            rec = (parse_updated(g('updated_at')), n,
                   [oid, clean_email(g('customer_email')), amt, cur, date, st])
            if oid not in best or (rec[0], rec[1]) >= (best[oid][0], best[oid][1]):
                best[oid] = rec
    res = sorted((r[2] for r in best.values()), key=lambda x: (x[4], x[0]))
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(COLS)
        w.writerows(res)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
