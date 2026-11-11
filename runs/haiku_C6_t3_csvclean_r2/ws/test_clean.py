"""Asserts for clean.py: spec examples, must-fail cases, and the sample file."""

import csv
import datetime
import os
import subprocess
import sys
import tempfile
from decimal import Decimal

import clean

HERE = os.path.dirname(os.path.abspath(__file__))


def amount(text):
    result = clean.parse_amount(text)
    return None if result is None else f"{result[0]:.2f}"


def date(text):
    result = clean.parse_date(text)
    return None if result is None else result.isoformat()


# --- amount: spec examples and rules ---
assert amount("2.005") == "2.01"
assert amount("(12.50)") == "-12.50"
assert amount("(1,000.005)") == "-1000.01"          # half away from zero
assert amount("$1,234.50") == "1234.50"
assert amount("1.234,56") == "1234.56"              # last separator is decimal
assert amount("1,234.56") == "1234.56"
assert amount("1,000") == "1000.00"                 # comma + 3 digits = thousands
assert amount("12,50") == "12.50"                   # comma + exactly 2 digits = decimal
assert amount("€ 7,5") == "75.00"                   # one digit after comma = thousands
assert amount("£3.10") == "3.10"
assert amount("99") == "99.00"
assert amount("(0.001)") == "0.00"                  # no "-0.00"
assert clean.parse_amount("€ 7,5")[1] == "€"
assert clean.parse_amount("99")[1] is None

# amount must-fail
for bad in ["", "   ", "$", "abc", "USD 12", "-12.50", "12.50-", "(12.50", "12.50)",
            "()", "1.2.3", "1,2.3.4", "12..5", "1.234.56", "1e3", "١٢"]:
    assert amount(bad) is None, bad

# --- dates: spec examples ---
for good, iso in [
    ("2026-03-04", "2026-03-04"),
    ("2026/03/04", "2026-03-04"),
    ("04.03.2026", "2026-03-04"),
    ("03/04/2026", "2026-03-04"),
    ("Mar 4, 2026", "2026-03-04"),
    ("March 4, 2026", "2026-03-04"),
    ("4 Mar 2026", "2026-03-04"),
    ("4 March 2026", "2026-03-04"),
    ("mar 4, 2026", "2026-03-04"),                  # any case
    ("2026-3-4", "2026-03-04"),                     # single digits in numeric forms
    ("2026/3/9", "2026-03-09"),
    ("  2026-03-04  ", "2026-03-04"),               # surrounding whitespace
]:
    assert date(good) == iso, good

# date must-fail
for bad in ["2026-02-30", "2026-13-01", "2026-00-10", "Mar 4 2026", "March 4 2026",
            "Mar  4, 2026", "Sept 4, 2026", "Mar 4, 26", "4 Mar, 2026", "26-03-04",
            "2026.03.04", "03-04-2026", "2026/03-04", "2026-03-04T10:00:00",
            "32.01.2026", "2026-03-04x", "", "Foo 4, 2026", "2026-03-04 extra"]:
    assert date(bad) is None, bad

# --- updated_at ---
assert clean.parse_updated_at("2026-03-04T10:00:00Z") == datetime.datetime(2026, 3, 4, 10)
assert clean.parse_updated_at("2026-03-05 09:00:00") == datetime.datetime(2026, 3, 5, 9)
assert clean.parse_updated_at("") == datetime.datetime.min
assert clean.parse_updated_at("2026-03-04T10:00") == datetime.datetime.min   # not the full form
assert clean.parse_updated_at("2026-02-30T10:00:00") == datetime.datetime.min

# --- email ---
assert clean.clean_email(" Alice@Example.COM ") == "alice@example.com"
for bad in ["carol@@example.com", "@example.com", "alice@", "alice", "a@b@c", " @ "]:
    assert clean.clean_email(bad) == "", bad

# --- currency ---
assert clean.clean_currency("", "€") == "EUR"
assert clean.clean_currency("", "£") == "GBP"
assert clean.clean_currency("", None) == "USD"
assert clean.clean_currency(" usd ", "€") == "USD"
assert clean.clean_currency("$", None) == "USD"
assert clean.clean_currency("gbp", None) == "GBP"

# --- status ---
assert clean.clean_status(" PAID ") == "paid"
assert clean.clean_status("Canceled") == "cancelled"
assert clean.clean_status("cancelled") == "cancelled"
for status in ["pending", "paid", "shipped", "cancelled", "refunded"]:
    assert clean.clean_status(status) == status
for bad in ["lost", "", "paid!", "cancel", "Canceled ed", "delivered"]:
    assert clean.clean_status(bad) == "unknown", bad

# --- end to end: sample file ---
out_dir = tempfile.mkdtemp()
out_path = os.path.join(out_dir, "out.csv")
subprocess.run([sys.executable, "-I", os.path.join(HERE, "clean.py"),
                os.path.join(HERE, "orders_raw.csv"), out_path], check=True)
with open(out_path, newline="", encoding="utf-8") as handle:
    raw = handle.read()
assert "\r" not in raw
rows = list(csv.reader(raw.splitlines(keepends=False)))
assert rows[0] == ["order_id", "customer_email", "amount", "currency", "order_date", "status"]
assert rows[1:] == [
    ["A-1001", "alice@example.com", "1300.00", "USD", "2026-03-04", "refunded"],
    ["A-1002", "bob@example.com", "99.00", "USD", "2026-03-04", "shipped"],
    ["A-1003", "", "1234.56", "EUR", "2026-03-04", "cancelled"],
    ["A-1006", "frank@example.com", "75.00", "EUR", "2026-03-07", "pending"],
    ["A-1007", "gina@example", "3.10", "GBP", "2026-03-09", "unknown"],
    ["A-1008", "hank@example.com", "1000.00", "GBP", "2026-03-10", "paid"],
    ["A-1010", "jack@example.com", "-1000.01", "USD", "2026-03-10", "paid"],
]

# --- end to end: dedup tie goes to the later row; BOM, comments, reordered columns ---
src = os.path.join(out_dir, "in.csv")
with open(src, "w", encoding="utf-8-sig", newline="") as handle:
    handle.write("# comment\n\n Status ,ORDER ID,Amount,Order Date,Updated At\n")
    handle.write("paid,x-1,1,2026-01-01,\n")
    handle.write("paid, x-1 ,2,2026-01-01,\n")
    handle.write("paid,x-2,3,2026-01-01,2026-01-01 00:00:00\n")
    handle.write("paid,x-2,4,2026-01-01,2026-01-01T00:00:00Z\n")
    handle.write("paid,,5,2026-01-01,\n")
    handle.write("paid,x-3,,2026-01-01,\n")
subprocess.run([sys.executable, "-I", os.path.join(HERE, "clean.py"), src, out_path], check=True)
with open(out_path, newline="", encoding="utf-8") as handle:
    rows = list(csv.reader(handle))
assert rows[1:] == [
    ["X-1", "", "2.00", "USD", "2026-01-01", "paid"],
    ["X-2", "", "4.00", "USD", "2026-01-01", "paid"],
], rows

print("all checks passed")
