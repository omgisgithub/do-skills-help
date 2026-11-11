#!/usr/bin/env python3
"""Normalize a shop order export: python3 clean.py INPUT.csv OUTPUT.csv."""

import argparse
import csv
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP, localcontext
import re


OUTPUT_FIELDS = ['order_id', 'customer_email', 'amount', 'currency',
                 'order_date', 'status']
CURRENCIES = {'$': 'USD', '€': 'EUR', '£': 'GBP'}
STATUSES = {'pending', 'paid', 'shipped', 'cancelled', 'refunded'}
MONTHS = {}
for number, name in enumerate(
        ('january', 'february', 'march', 'april', 'may', 'june',
         'july', 'august', 'september', 'october', 'november', 'december'), 1):
    MONTHS[name] = MONTHS[name[:3]] = number


def parse_amount(value):
    """Apply the export's separator rules and round without float errors."""
    value = ''.join(char for char in value
                    if not char.isspace() and char not in CURRENCIES)
    negative = value.startswith('(') and value.endswith(')')
    if negative:
        value = value[1:-1]
        if value.startswith(('+', '-')):
            raise ValueError('Signed accounting amount')

    if '.' in value and ',' in value:
        if value.rfind('.') > value.rfind(','):
            value = value.replace(',', '')
        else:
            value = value.replace('.', '').replace(',', '.')
    elif ',' in value:
        whole, fractional = value.rsplit(',', 1)
        if re.fullmatch(r'[0-9]{2}', fractional):
            value = whole.replace(',', '') + '.' + fractional
        else:
            value = value.replace(',', '')

    if not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)', value):
        raise ValueError('Invalid amount')
    amount = Decimal(('-' if negative else '') + value)
    # Leave room for large integer parts and a carry during rounding.
    with localcontext() as context:
        context.prec = max(28, len(value) + 3)
        return format(amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), '.2f')


def parse_date(value):
    """Parse only the documented formats, with locale-independent months."""
    for pattern, order in (
            (r'([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})', (0, 1, 2)),
            (r'([0-9]{4})/([0-9]{1,2})/([0-9]{1,2})', (0, 1, 2)),
            (r'([0-9]{1,2})\.([0-9]{1,2})\.([0-9]{4})', (2, 1, 0)),
            (r'([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})', (2, 0, 1))):
        match = re.fullmatch(pattern, value)
        if match:
            parts = [int(part) for part in match.groups()]
            return date(*(parts[index] for index in order)).isoformat()

    match = re.fullmatch(r'([A-Za-z]+)\s+([0-9]{1,2}),\s+([0-9]{4})', value)
    if match:
        month, day, year = match.groups()
    else:
        match = re.fullmatch(r'([0-9]{1,2})\s+([A-Za-z]+)\s+([0-9]{4})', value)
        if not match:
            raise ValueError('Invalid date format')
        day, month, year = match.groups()
    month_number = MONTHS.get(month.lower())
    if month_number is None:
        raise ValueError('Invalid month')
    return date(int(year), month_number, int(day)).isoformat()


def parse_updated_at(value):
    if not value:
        return datetime.min
    try:
        return datetime.strptime(value.rstrip('Z').replace('T', ' '),
                                 '%Y-%m-%d %H:%M:%S')
    except ValueError:
        # Malformed timestamps have no usable recency information.
        return datetime.min


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
                   for name in OUTPUT_FIELDS + ['updated_at']}
            row['order_id'] = row['order_id'].upper()
            if not row['order_id']:
                continue
            amount_source = row['amount']
            try:
                row['amount'] = parse_amount(amount_source)
                row['order_date'] = parse_date(row['order_date'])
            except ValueError:
                continue

            email = row['customer_email'].lower()
            parts = email.split('@')
            row['customer_email'] = email if len(parts) == 2 and all(parts) else ''
            currency = row['currency'].upper()
            if not currency:
                currency = next((CURRENCIES[char] for char in amount_source
                                 if char in CURRENCIES), 'USD')
            row['currency'] = CURRENCIES.get(currency, currency)
            status = row['status'].lower()
            if status == 'canceled':
                status = 'cancelled'
            row['status'] = status if status in STATUSES else 'unknown'
            updated_at = parse_updated_at(row.pop('updated_at'))
            previous = latest.get(row['order_id'])
            if previous is None or updated_at >= previous[0]:
                latest[row['order_id']] = (updated_at, row)

    rows = sorted((entry[1] for entry in latest.values()),
                  key=lambda row: (row['order_date'], row['order_id']))
    with open(output_path, 'w', encoding='utf-8', newline='') as destination:
        writer = csv.DictWriter(destination, fieldnames=OUTPUT_FIELDS, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input_csv')
    parser.add_argument('output_csv')
    args = parser.parse_args()
    clean(args.input_csv, args.output_csv)


if __name__ == '__main__':
    main()
