#!/usr/bin/env python3
"""Clean a messy order export: python3 clean.py INPUT.csv OUTPUT.csv"""
import csv
import re
import sys
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

SYMBOLS = {'$': 'USD', '€': 'EUR', '£': 'GBP'}
STATUSES = {'pending', 'paid', 'shipped', 'cancelled', 'refunded'}
MONTHS = {}
for _i, _name in enumerate('january february march april may june july august september '
                            'october november december'.split(), 1):
    MONTHS[_name] = MONTHS[_name[:3]] = _i
DATE_RES = [re.compile(p) for p in (
    r'(?P<y>\d{4})[-/](?P<m>\d{1,2})[-/](?P<d>\d{1,2})',
    r'(?P<d>\d{1,2})\.(?P<m>\d{1,2})\.(?P<y>\d{4})',
    r'(?P<m>\d{1,2})/(?P<d>\d{1,2})/(?P<y>\d{4})',
    r'(?P<mon>[A-Za-z]+)\.? (?P<d>\d{1,2}),? (?P<y>\d{4})',
    r'(?P<d>\d{1,2}) (?P<mon>[A-Za-z]+),? (?P<y>\d{4})',
)]
TS_RE = re.compile(r'(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})Z?')


def parse_amount(raw):
    s = re.sub(r'[\s$€£]', '', raw)
    neg = '(' in s or '-' in s
    s = re.sub(r'[()\-]', '', s)
    if '.' in s and ',' in s:
        dec = '.' if s.rfind('.') > s.rfind(',') else ','
    elif ',' in s:
        dec = ',' if len(s) - s.rfind(',') == 3 else None  # exactly two digits after last comma
    else:
        dec = '.'
    if dec == ',':
        head, _, tail = s.rpartition(',')
        s = head.replace('.', '').replace(',', '') + '.' + tail
    else:
        s = s.replace(',', '')
    if not re.fullmatch(r'\d+\.?\d*|\.\d+', s):
        return None
    value = Decimal(s).quantize(Decimal('0.01'), ROUND_HALF_UP)  # half away from zero on the magnitude
    return -value if neg and value else value


def parse_date(s):
    for pat in DATE_RES:
        m = pat.fullmatch(s)
        if m:
            g = m.groupdict()
            month = MONTHS.get(g['mon'].lower()) if 'mon' in g else int(g['m'])
            try:
                return date(int(g['y']), month, int(g['d'])).isoformat()
            except (TypeError, ValueError):
                return None
    return None


def main(src, dst):
    with open(src, encoding='utf-8-sig', newline='') as f:
        lines = [ln for ln in f.read().splitlines() if ln.strip() and not ln.startswith('#')]
    rows = csv.reader(lines)
    header = [h.strip().lower().replace(' ', '_') for h in next(rows)]
    idx = {h: i for i, h in enumerate(header)}

    best = {}  # order_id -> (updated_at key, record)
    for row in rows:
        c = {name: row[i].strip() if i < len(row) else '' for name, i in idx.items()}
        oid = c['order_id'].upper()
        amount = parse_amount(c['amount']) if oid else None
        order_date = parse_date(c['order_date']) if amount is not None else None
        if order_date is None:
            continue

        cur = c['currency'].upper()
        symbol = next((SYMBOLS[ch] for ch in c['amount'] if ch in SYMBOLS), None)
        currency = SYMBOLS.get(cur, cur) if cur else (symbol or 'USD')

        email = c['customer_email'].lower()
        parts = email.split('@')
        if len(parts) != 2 or not all(parts):
            email = ''

        status = c['status'].lower()
        status = 'cancelled' if status == 'canceled' else status
        if status not in STATUSES:
            status = 'unknown'

        m = TS_RE.fullmatch(c.get('updated_at', ''))
        key = m.group(1) + 'T' + m.group(2) if m else ''

        rec = (oid, email, str(amount), currency, order_date, status)
        if oid not in best or key >= best[oid][0]:  # ties: later row in file wins
            best[oid] = (key, rec)

    out = sorted((rec for _, rec in best.values()), key=lambda r: (r[4], r[0]))
    with open(dst, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['order_id', 'customer_email', 'amount', 'currency', 'order_date', 'status'])
        w.writerows(out)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
