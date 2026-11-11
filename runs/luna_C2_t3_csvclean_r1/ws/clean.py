import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


FIELDS = ('order_id', 'customer_email', 'amount', 'currency', 'order_date', 'status')
SYMBOLS = {'$': 'USD', '€': 'EUR', '£': 'GBP'}
DATE_FORMATS = ('%Y-%m-%d', '%Y/%m/%d', '%d.%m.%Y', '%m/%d/%Y',
                '%b %d %Y', '%B %d %Y', '%b %d, %Y', '%B %d, %Y',
                '%d %b %Y', '%d %B %Y')


def amount_value(value):
    value = value.strip()
    symbol = next((currency for symbol, currency in SYMBOLS.items() if symbol in value), '')
    value = re.sub(r'[$€£\s]', '', value)
    negative = value.startswith('(') and value.endswith(')')
    if negative:
        value = value[1:-1]
    if ',' in value and '.' in value:
        decimal_sep = '.' if value.rfind('.') > value.rfind(',') else ','
    elif ',' in value:
        decimal_sep = ',' if len(value) - value.rfind(',') - 1 == 2 else '.'
    else:
        decimal_sep = '.'
    thousands_sep = ',' if decimal_sep == '.' else '.'
    value = value.replace(thousands_sep, '').replace(decimal_sep, '.')
    try:
        amount = Decimal(value)
        if not amount.is_finite():
            return None, symbol
        if negative:
            amount = -amount
        return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), symbol
    except InvalidOperation:
        return None, symbol


def order_date(value):
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return ''


def clean_row(row):
    order_id = (row.get('order_id') or '').strip().upper()
    amount, symbol_currency = amount_value(row.get('amount') or '')
    day = order_date(row.get('order_date') or '')
    if not order_id or amount is None or not day:
        return None
    email = (row.get('customer_email') or '').strip().lower()
    if email.count('@') != 1 or not all(email.split('@')):
        email = ''
    currency = (row.get('currency') or '').strip().upper()
    currency = SYMBOLS.get(currency, currency) if currency else symbol_currency or 'USD'
    status = (row.get('status') or '').strip().lower()
    if status == 'canceled':
        status = 'cancelled'
    if status not in ('pending', 'paid', 'shipped', 'cancelled', 'refunded'):
        status = 'unknown'
    updated = (row.get('updated_at') or '').strip().replace(' ', 'T')
    if updated.endswith('Z'):
        updated = updated[:-1]
    return order_id, email, format(amount, '.2f'), currency, day, status, updated


def main(source, destination):
    with open(source, encoding='utf-8-sig', newline='') as infile:
        lines = (line for line in infile if line.strip() and not line.startswith('#'))
        reader = csv.DictReader(lines)
        headers = [(name or '').strip().lower().replace(' ', '_') for name in (reader.fieldnames or [])]
        reader.fieldnames = headers
        latest = {}
        for index, row in enumerate(reader):
            cleaned = clean_row(row)
            if cleaned is None:
                continue
            previous = latest.get(cleaned[0])
            if previous is None or (cleaned[6], index) >= (previous[0], previous[1]):
                latest[cleaned[0]] = (cleaned[6], index, cleaned[:6])
    rows = sorted((item[2] for item in latest.values()), key=lambda row: (row[4], row[0]))
    with open(destination, 'w', encoding='utf-8', newline='') as outfile:
        writer = csv.writer(outfile, lineterminator='\n')
        writer.writerow(FIELDS)
        writer.writerows(rows)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: python3 clean.py INPUT.csv OUTPUT.csv')
    main(sys.argv[1], sys.argv[2])
