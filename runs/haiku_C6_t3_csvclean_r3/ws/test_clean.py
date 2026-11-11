import csv
import os
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal

import clean

HERE = os.path.dirname(os.path.abspath(__file__))


def amount(raw):
    parsed = clean.parse_amount(raw)
    return None if parsed is None else clean.format_amount(parsed[0])


class HeaderTests(unittest.TestCase):
    def test_header_normalised(self):
        index = clean.header_index([" Order ID ", "Customer Email", "Updated At"])
        self.assertEqual(index, {"order_id": 0, "customer_email": 1, "updated_at": 2})


class AmountTests(unittest.TestCase):
    def test_examples(self):
        self.assertEqual(amount("$1,234.50"), "1234.50")
        self.assertEqual(amount("99"), "99.00")
        self.assertEqual(amount("1.234,56"), "1234.56")
        self.assertEqual(amount("(12.50)"), "-12.50")
        self.assertEqual(amount("2.005"), "2.01")
        self.assertEqual(amount("(1,000.005)"), "-1000.01")
        self.assertEqual(amount("€ 7,5"), "75.00")
        self.assertEqual(amount("£3.10"), "3.10")
        self.assertEqual(amount("1,000"), "1000.00")
        self.assertEqual(amount("1,00"), "1.00")
        self.assertEqual(amount("1,234,567"), "1234567.00")
        self.assertEqual(amount("-$12.5"), "-12.50")

    def test_currency_symbol_detected(self):
        self.assertEqual(clean.parse_amount("£3.10")[1], "£")
        self.assertIsNone(clean.parse_amount("12.50")[1])

    def test_negative_cases(self):
        self.assertIsNone(amount(""))
        self.assertIsNone(amount("$"))
        self.assertIsNone(amount("abc"))
        self.assertIsNone(amount("1.2.3"))
        self.assertIsNone(amount("12 USD"))
        self.assertIsNone(amount("--1"))
        self.assertIsNone(amount("(-5)"))
        self.assertIsNone(amount("1.234.567"))
        self.assertIsNone(amount("+5"))

    def test_zero_has_no_sign(self):
        self.assertEqual(amount("(0.001)"), "0.00")


class DateTests(unittest.TestCase):
    def test_accepted_forms(self):
        for raw in ["2026-03-04", "2026/03/04", "04.03.2026", "03/04/2026",
                    "Mar 4, 2026", "March 4, 2026", "4 Mar 2026", "4 March 2026",
                    "mar 4, 2026", "2026/3/4", "3/4/2026", "4 march 2026"]:
            with self.subTest(raw=raw):
                self.assertEqual(clean.parse_date(raw), "2026-03-04")

    def test_negative_cases(self):
        for raw in ["Mar 4 2026", "2026-02-30", "2026-13-01", "03-04-2026",
                    "2026.03.04", "04/03/2026-", "2026-03-04T10:00:00",
                    "March 4 2026", "4, Mar 2026", "Mar 04 2026", "Foo 4, 2026",
                    "26-03-04", "2026-02-29", "31.04.2026", "Mar 4, 26", ""]:
            with self.subTest(raw=raw):
                self.assertIsNone(clean.parse_date(raw))

    def test_surrounding_space_trimmed(self):
        self.assertEqual(clean.parse_date(" 2026-03-4 "), "2026-03-04")


class StatusTests(unittest.TestCase):
    def test_mapping(self):
        self.assertEqual(clean.clean_status(" PAID "), "paid")
        self.assertEqual(clean.clean_status("Canceled"), "cancelled")
        self.assertEqual(clean.clean_status("cancelled"), "cancelled")

    def test_unknown(self):
        self.assertEqual(clean.clean_status("lost"), "unknown")
        self.assertEqual(clean.clean_status(""), "unknown")
        self.assertEqual(clean.clean_status("in transit"), "unknown")


class EmailTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(clean.clean_email(" Alice@Example.COM "), "alice@example.com")
        self.assertEqual(clean.clean_email("gina@example"), "gina@example")

    def test_invalid(self):
        for raw in ["carol@@example.com", "a@b@c", "@x", "x@", "nope", ""]:
            with self.subTest(raw=raw):
                self.assertEqual(clean.clean_email(raw), "")


class UpdatedAtTests(unittest.TestCase):
    def test_forms_order(self):
        a = clean.parse_updated_at("2026-03-05 09:00:00")
        b = clean.parse_updated_at("2026-03-05T09:00:00Z")
        self.assertEqual(a, b)
        self.assertGreater(a, clean.parse_updated_at(""))

    def test_empty_and_malformed_are_oldest(self):
        self.assertEqual(clean.parse_updated_at(""), clean.OLDEST)
        self.assertEqual(clean.parse_updated_at("2026-03-05"), clean.OLDEST)
        self.assertEqual(clean.parse_updated_at("2026-03-05t09:00:00"), clean.OLDEST)


def run_cli(text):
    tmp = tempfile.mkdtemp()
    src = os.path.join(tmp, "in.csv")
    dst = os.path.join(tmp, "out.csv")
    with open(src, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    subprocess.run([sys.executable, "-I", os.path.join(HERE, "clean.py"), src, dst], check=True)
    with open(dst, encoding="utf-8", newline="") as f:
        return f.read()


class DedupeAndSampleTests(unittest.TestCase):
    def test_bom_comments_blank_lines_and_dedupe(self):
        text = ("﻿ Order ID ,Amount,Order Date,Status,Updated At\n"
                "# comment\n"
                "\n"
                "a-1,$5,2026-01-02,paid,2026-01-02T00:00:00\n"
                "A-1,$6,2026-01-02,paid,2026-01-01T00:00:00\n"
                "A-2,$7,2026-01-02,paid,\n"
                "A-2,$8,2026-01-02,paid,\n")
        self.assertEqual(run_cli(text),
                         "order_id,customer_email,amount,currency,order_date,status\n"
                         "A-1,,5.00,USD,2026-01-02,paid\n"
                         "A-2,,8.00,USD,2026-01-02,paid\n")

    def test_tie_keeps_later_and_bad_rows_do_not_compete(self):
        text = ("order_id,amount,order_date,status,updated_at\n"
                "B-1,1,2026-01-01,paid,2026-01-01T00:00:00\n"
                "B-1,2,2026-01-01,paid,2026-01-01T00:00:00\n"
                "B-1,,2026-01-01,paid,2099-01-01T00:00:00\n")
        self.assertIn("B-1,,2.00,USD,2026-01-01,paid", run_cli(text))

    def test_sort_by_date_then_id(self):
        text = ("order_id,amount,order_date,status\n"
                "Z,1,2026-02-01,paid\n"
                "A,1,2026-02-01,paid\n"
                "M,1,2026-01-01,paid\n")
        rows = list(csv.reader(run_cli(text).splitlines()))
        self.assertEqual([r[0] for r in rows[1:]], ["M", "A", "Z"])

    def test_sample_file(self):
        with open(os.path.join(HERE, "orders_raw.csv"), encoding="utf-8", newline="") as f:
            text = f.read()
        self.assertEqual(run_cli(text),
                         "order_id,customer_email,amount,currency,order_date,status\n"
                         "A-1001,alice@example.com,1300.00,USD,2026-03-04,refunded\n"
                         "A-1002,bob@example.com,99.00,USD,2026-03-04,shipped\n"
                         "A-1003,,1234.56,EUR,2026-03-04,cancelled\n"
                         "A-1006,frank@example.com,75.00,EUR,2026-03-07,pending\n"
                         "A-1007,gina@example,3.10,GBP,2026-03-09,unknown\n"
                         "A-1008,hank@example.com,1000.00,GBP,2026-03-10,paid\n"
                         "A-1010,jack@example.com,-1000.01,USD,2026-03-10,paid\n")


if __name__ == "__main__":
    unittest.main()
