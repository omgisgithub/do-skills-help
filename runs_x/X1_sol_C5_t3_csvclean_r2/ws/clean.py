#!/usr/bin/env python3
"""Normalize an order export: python3 clean.py INPUT.csv OUTPUT.csv."""

import argparse
import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import re


OUTPUT_FIELDS = ('order_id', 'customer_email', 'amount', 'currency', 'order_date', 'status')
CURRENCIES = {'$': 'USD', '€': 'EUR', '£': 'GBP'}
STATUSES = {'pending', 'paid', 'shipped', 'cancelled', 'refunded'}
MONTHS = {}
for number, name in enumerate(('january', 'february', 'march', 'april', 'may', 'june',
                               'july', 'august', 'september', 'october', 'november',
                               'december'), 1):
    MONTHS[name] = MONTHS[name[:3]] = number


def parse_amount(value):
    """Apply the export's separator rules and round without binary floats."""
    value = ''.join(char for char in value if not char.isspace() and char not in CURRENCIES)
    negative = value.startswith('(') and value.endswith(')')
    if negative:
        value = value[1:-1]
    if '.' in value and ',' in value:
        decimal = '.' if value.rfind('.') > value.rfind(',') else ','
        thousands = ',' if decimal == '.' else '.'
        value = value.replace(thousands, '').replace(decimal, '.')
    elif ',' in value:
        tail = value.rsplit(',', 1)[1]
        if re.fullmatch(r'[0-9]{2}', tail):
            whole, fraction = value.rsplit(',', 1)
            value = whole.replace(',', '') + '.' + fraction
        else:
            value = value.replace(',', '')
    if not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)', value):
        raise ValueError('Invalid amount')
    if negative and value.startswith(('+', '-')):
        raise ValueError('Conflicting amount signs')
    with localcontext() as context:
        context.prec = max(28, len(value) + 4)
        amount = Decimal(value)
        if negative:
            amount = -amount
        return format(amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), '.2f')


def parse_date(value):
    """Accept only the documented numeric and English month formats."""
    for pattern, order in (
        (r'([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})', 'ymd'),
        (r'([0-9]{4})/([0-9]{1,2})/([0-9]{1,2})', 'ymd'),
        (r'([0-9]{1,2})\.([0-9]{1,2})\.([0-9]{4})', 'dmy'),
        (r'([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})', 'mdy'),
    ):
        match = re.fullmatch(pattern, value)
        if match:
            parts = dict(zip(order, map(int, match.groups())))
            return date(parts['y'], parts['m'], parts['d']).isoformat()
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
    # All specified timestamps use the same time basis, with an optional Z.
    if re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}Z?', value):
        try:
            return datetime.strptime(value.rstrip('Z').replace('T', ' '), '%Y-%m-%d %H:%M:%S')
        except ValueError:
            pass
    # Malformed timestamps, like missing ones, have no usable update time.
    return datetime.min


def clean_orders(input_path, output_path):
    orders = {}
    with open(input_path, encoding='utf-8-sig', newline='') as source:
        lines = (line for line in source if line.strip() and not line.startswith('#'))
        reader = csv.DictReader(lines, skipinitialspace=True)
        if reader.fieldnames is not None:
            reader.fieldnames = [name.strip().lower().replace(' ', '_') for name in reader.fieldnames]
        for raw in reader:
            row = {name: (raw.get(name) or '').strip()
                   for name in OUTPUT_FIELDS + ('updated_at',)}
            order_id = row['order_id'].upper()
            if not order_id:
                continue
            try:
                amount = parse_amount(row['amount'])
                order_date = parse_date(row['order_date'])
            except (ValueError, InvalidOperation):
                continue

            email = row['customer_email'].lower()
            if email.count('@') != 1 or not all(email.split('@')):
                email = ''
            currency = row['currency'].upper()
            if not currency:
                currency = next((CURRENCIES[char] for char in row['amount'] if char in CURRENCIES), 'USD')
            currency = CURRENCIES.get(currency, currency)
            status = row['status'].lower()
            if status == 'canceled':
                status = 'cancelled'
            if status not in STATUSES:
                status = 'unknown'
            updated_at = parse_updated_at(row['updated_at'])
            cleaned = (order_id, email, amount, currency, order_date, status)
            if order_id not in orders or updated_at >= orders[order_id][0]:
                orders[order_id] = (updated_at, cleaned)

    with open(output_path, 'w', encoding='utf-8', newline='') as target:
        writer = csv.writer(target, lineterminator='\n')
        writer.writerow(OUTPUT_FIELDS)
        writer.writerows(sorted((item[1] for item in orders.values()),
                               key=lambda row: (row[4], row[0])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input_csv')
    parser.add_argument('output_csv')
    args = parser.parse_args()
    clean_orders(args.input_csv, args.output_csv)


if __name__ == '__main__':
    main()
