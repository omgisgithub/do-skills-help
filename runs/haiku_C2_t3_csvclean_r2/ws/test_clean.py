import os
import tempfile
import unittest
from decimal import Decimal

import clean

HERE = os.path.dirname(os.path.abspath(__file__))


class CleanTest(unittest.TestCase):
    def test_amounts(self):
        cases = {
            "$1,234.50": ("1234.50", "USD"),
            "1.234,56": ("1234.56", ""),
            "€ 7,5": ("75.00", "EUR"),
            "1,000": ("1000.00", ""),
            "(12.50)": ("-12.50", ""),
            "(1,000.005)": ("-1000.01", ""),
            "2.005": ("2.01", ""),
        }
        for text, (amount, currency) in cases.items():
            got = clean.parse_amount(text)
            self.assertEqual((f"{got[0]:.2f}", got[1]), (amount, currency), text)
        self.assertIsNone(clean.parse_amount(""))
        self.assertIsNone(clean.parse_amount("1.2.3"))

    def test_dates(self):
        self.assertEqual(clean.parse_date("03/04/2026"), "2026-03-04")
        self.assertEqual(clean.parse_date("04.03.2026"), "2026-03-04")
        self.assertEqual(clean.parse_date("March 10, 2026"), "2026-03-10")
        self.assertEqual(clean.parse_date("7 march 2026"), "2026-03-07")
        self.assertEqual(clean.parse_date("2026/3/9"), "2026-03-09")
        self.assertIsNone(clean.parse_date("Mar 4 2026"))
        self.assertIsNone(clean.parse_date("2026-02-30"))

    def test_sample_export(self):
        expected = (
            "order_id,customer_email,amount,currency,order_date,status\n"
            "A-1001,alice@example.com,1300.00,USD,2026-03-04,refunded\n"
            "A-1002,bob@example.com,99.00,USD,2026-03-04,shipped\n"
            "A-1003,,1234.56,EUR,2026-03-04,cancelled\n"
            "A-1006,frank@example.com,75.00,EUR,2026-03-07,pending\n"
            "A-1007,gina@example,3.10,GBP,2026-03-09,unknown\n"
            "A-1008,hank@example.com,1000.00,GBP,2026-03-10,paid\n"
            "A-1010,jack@example.com,-1000.01,USD,2026-03-10,paid\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            dst = os.path.join(tmp, "out.csv")
            clean.main(os.path.join(HERE, "orders_raw.csv"), dst)
            with open(dst, encoding="utf-8", newline="") as f:
                self.assertEqual(f.read(), expected)


if __name__ == "__main__":
    unittest.main()
