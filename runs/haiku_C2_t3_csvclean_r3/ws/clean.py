"""Clean a messy order export: python3 clean.py INPUT.csv OUTPUT.csv"""
import csv
import re
import sys
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

SOURCE_FIELDS = ['order_id', 'customer_email', 'amount', 'currency', 'order_date', 'status', 'updated_at']
OUTPUT_FIELDS = ['order_id', 'customer_email', 'amount', 'currency', 'order_date', 'status']
SYMBOLS = {'$': 'USD', '€': 'EUR', '£': 'GBP'}
STATUSES = {'pending', 'paid', 'shipped', 'cancelled', 'refunded'}
DATE_FORMATS = ['%Y-%m-%d', '%Y/%m/%d', '%d.%m.%Y', '%m/%d/%Y',
                '%B %d, %Y', '%b %d, %Y', '%d %B %Y', '%d %b %Y']


def parse_amount(raw):
    s = re.sub(r'[\s$€£]', '', raw)
    if s.startswith('(') and s.endswith(')'):
        neg, s = True, s[1:-1]
    elif s.startswith('-'):
        neg, s = True, s[1:]
    else:
        neg = False
    if '.' in s and ',' in s:
        s = s.replace(',', '') if s.rfind('.') > s.rfind(',') else s.replace('.', '').replace(',', '.')
    elif ',' in s:
        head, _, tail = s.rpartition(',')
        s = head.replace(',', '') + '.' + tail if re.fullmatch(r'\d{2}', tail) else s.replace(',', '')
    if not re.fullmatch(r'\d*\.?\d+', s):
        return None
    try:
        value = Decimal(s).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None
    return -value if neg and value else value


def parse_date(raw):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def parse_ts(raw):
    try:
        return datetime.strptime(raw.rstrip('Z').replace(' ', 'T'), '%Y-%m-%dT%H:%M:%S')
    except ValueError:
        return datetime.min


def clean(row):
    row = {k: (row.get(k) or '').strip() for k in SOURCE_FIELDS}
    amount = parse_amount(row['amount'])
    order_date = parse_date(row['order_date'])
    order_id = row['order_id'].upper()
    if not order_id or amount is None or order_date is None:
        return None
    email = row['customer_email'].lower()
    if email.count('@') != 1 or not all(email.partition('@')[::2]):
        email = ''
    currency = row['currency'].upper() or next((SYMBOLS[c] for c in row['amount'] if c in SYMBOLS), 'USD')
    currency = SYMBOLS.get(currency, currency)
    status = row['status'].lower()
    status = 'cancelled' if status == 'canceled' else status
    if status not in STATUSES:
        status = 'unknown'
    return {
        'order_id': order_id,
        'customer_email': email,
        'amount': f'{amount:.2f}',
        'currency': currency,
        'order_date': order_date,
        'status': status,
        'updated_at': row['updated_at'],
    }


def main(src, dst):
    with open(src, encoding='utf-8-sig', newline='') as f:
        lines = [line for line in f if line.strip() and not line.startswith('#')]
    reader = csv.DictReader(lines, restval='')
    reader.fieldnames = [h.strip().lower().replace(' ', '_') for h in reader.fieldnames or []]
    best = {}
    for row in reader:
        rec = clean(row)
        if rec is None:
            continue
        ts = parse_ts(rec['updated_at'])
        if rec['order_id'] not in best or ts >= best[rec['order_id']][0]:
            best[rec['order_id']] = (ts, rec)
    out = sorted((rec for _, rec in best.values()), key=lambda r: (r['order_date'], r['order_id']))
    with open(dst, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, OUTPUT_FIELDS, extrasaction='ignore', lineterminator='\n')
        writer.writeheader()
        writer.writerows(out)


if __name__ == '__main__':
    main(*sys.argv[1:3])
