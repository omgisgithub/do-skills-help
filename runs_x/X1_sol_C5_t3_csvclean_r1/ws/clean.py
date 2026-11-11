"""Normalize shop order exports using only the Python 3.9 standard library."""

import argparse
import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import re


OUTPUT_FIELDS = ('order_id', 'customer_email', 'amount', 'currency',
                 'order_date', 'status')
SYMBOLS = {'$': 'USD', '€': 'EUR', '£': 'GBP'}
STATUSES = {'pending', 'paid', 'shipped', 'cancelled', 'refunded'}
MONTHS = {}
for number, name in enumerate(
        ('january', 'february', 'march', 'april', 'may', 'june', 'july',
         'august', 'september', 'october', 'november', 'december'), 1):
    MONTHS[name] = number
    MONTHS[name[:3]] = number


def parse_amount(raw):
    """Return a fixed-point amount, rejecting malformed or nonfinite numbers."""
    value = ''.join(char for char in raw
                    if not char.isspace() and char not in SYMBOLS)
    negative = value.startswith('(') and value.endswith(')')
    if negative:
        value = value[1:-1]
        if value.startswith(('+', '-')):
            raise ValueError('Accounting amount also has a sign')
    if '.' in value and ',' in value:
        decimal = '.' if value.rfind('.') > value.rfind(',') else ','
        thousands = ',' if decimal == '.' else '.'
        value = value.replace(thousands, '').replace(decimal, '.')
    elif ',' in value:
        before, after = value.rsplit(',', 1)
        if re.fullmatch(r'[0-9]{2}', after):
            value = before.replace(',', '') + '.' + after
        else:
            value = value.replace(',', '')
    if not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)', value):
        raise ValueError('Invalid amount')
    amount = Decimal(('-' if negative else '') + value)
    # Quantizing must also work for amounts larger than Decimal's default precision.
    with localcontext() as context:
        context.prec = max(28, len(amount.as_tuple().digits) + 2)
        return format(amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), '.2f')


def parse_date(raw):
    """Parse only the specified numeric forms and English month names."""
    match = re.fullmatch(r'([0-9]{4})([-/])([0-9]{1,2})\2([0-9]{1,2})', raw)
    if match:
        year, month, day = int(match[1]), int(match[3]), int(match[4])
    else:
        match = re.fullmatch(r'([0-9]{1,2})([./])([0-9]{1,2})\2([0-9]{4})', raw)
        if match:
            first, second, year = int(match[1]), int(match[3]), int(match[4])
            day, month = (first, second) if match[2] == '.' else (second, first)
        else:
            match = re.fullmatch(r'([A-Za-z]+)\s+([0-9]{1,2}),\s+([0-9]{4})', raw)
            if match:
                month = MONTHS.get(match[1].lower(), 0)
                day, year = int(match[2]), int(match[3])
            else:
                match = re.fullmatch(r'([0-9]{1,2})\s+([A-Za-z]+)\s+([0-9]{4})', raw)
                if not match:
                    raise ValueError('Invalid date format')
                day, year = int(match[1]), int(match[3])
                month = MONTHS.get(match[2].lower(), 0)
    return date(year, month, day).isoformat()


def parse_updated_at(raw):
    """Compare all supported timestamps on the same timezone-free basis."""
    if re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}Z?', raw):
        try:
            return (1, datetime.strptime(raw.rstrip('Z').replace('T', ' '),
                                         '%Y-%m-%d %H:%M:%S'))
        except ValueError:
            pass
    # The export defines no invalid-timestamp rule; treat it like a missing one.
    return (0, datetime.min)


def clean(input_path, output_path):
    latest = {}
    with open(input_path, encoding='utf-8-sig', newline='') as source:
        lines = (line for line in source if line.strip() and not line.startswith('#'))
        reader = csv.DictReader(lines)
        if reader.fieldnames is not None:
            reader.fieldnames = [name.strip().lower().replace(' ', '_')
                                for name in reader.fieldnames]
        for raw in reader:
            row = {name: (raw.get(name) or '').strip()
                   for name in OUTPUT_FIELDS + ('updated_at',)}
            row['order_id'] = row['order_id'].upper()
            if not row['order_id']:
                continue
            raw_amount = row['amount']
            try:
                row['amount'] = parse_amount(raw_amount)
                row['order_date'] = parse_date(row['order_date'])
            except (ValueError, InvalidOperation):
                continue
            email = row['customer_email'].lower()
            parts = email.split('@')
            row['customer_email'] = email if len(parts) == 2 and all(parts) else ''
            currency = row['currency'].upper()
            if not currency:
                currency = next((SYMBOLS[c] for c in raw_amount if c in SYMBOLS), 'USD')
            row['currency'] = SYMBOLS.get(currency, currency)
            status = row['status'].lower()
            if status == 'canceled':
                status = 'cancelled'
            row['status'] = status if status in STATUSES else 'unknown'
            timestamp = parse_updated_at(row.pop('updated_at'))
            previous = latest.get(row['order_id'])
            if previous is None or timestamp >= previous[0]:
                latest[row['order_id']] = (timestamp, row)

    rows = sorted((entry[1] for entry in latest.values()),
                  key=lambda row: (row['order_date'], row['order_id']))
    with open(output_path, 'w', encoding='utf-8', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=OUTPUT_FIELDS, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', metavar='INPUT.csv')
    parser.add_argument('output', metavar='OUTPUT.csv')
    args = parser.parse_args()
    clean(args.input, args.output)


if __name__ == '__main__':
    main()
