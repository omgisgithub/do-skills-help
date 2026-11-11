import os
import subprocess
import sys

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)  # python3 -I drops the script dir from sys.path
from clean import parse_amount, parse_date  # noqa: E402

assert str(parse_amount('$1,234.50')) == '1234.50'
assert str(parse_amount('1.234,56')) == '1234.56'
assert str(parse_amount('(12.50)')) == '-12.50'
assert str(parse_amount('2.005')) == '2.01'
assert str(parse_amount('(1,000.005)')) == '-1000.01'
assert str(parse_amount('1,000')) == '1000.00'
assert str(parse_amount('1,234,56')) == '1234.56'
assert parse_amount('') is None and parse_amount('abc') is None

assert parse_date('2026/3/9') == '2026-03-09'
assert parse_date('04.03.2026') == '2026-03-04'
assert parse_date('03/04/2026') == '2026-03-04'
assert parse_date('March 10, 2026') == '2026-03-10'
assert parse_date('7 march 2026') == '2026-03-07'
assert parse_date('Mar 4 2026') is None
assert parse_date('2026-02-30') is None

out = os.path.join(here, 'orders_test_out.csv')
subprocess.run([sys.executable, '-I', os.path.join(here, 'clean.py'),
                os.path.join(here, 'orders_raw.csv'), out], check=True)
with open(out, encoding='utf-8') as f:
    lines = f.read().splitlines()
assert lines[0] == 'order_id,customer_email,amount,currency,order_date,status', lines[0]
assert 'A-1001,alice@example.com,1300.00,USD,2026-03-04,refunded' in lines, lines
assert 'A-1010,jack@example.com,-1000.01,USD,2026-03-10,paid' in lines, lines
assert all(not line.startswith('A-1004') and not line.startswith('A-1009') for line in lines), lines
print('ok')
