import csv
import os
import tempfile
import unittest
from datetime import date
from decimal import Decimal

import clean


class ParseTests(unittest.TestCase):
    def test_amount(self):
        cases = {
            "$1,234.50": "1234.50",
            "1.234,56": "1234.56",
            "1,000": "1000.00",
            "7,5": "75.00",
            "(12.50)": "-12.50",
            "2.005": "2.01",
            "-2.005": "-2.01",
            "€ 1 000,00": "1000.00",
            "()": None,
            "": None,
            "abc": None,
            "1.2.3": None,
        }
        for raw, expected in cases.items():
            got = clean.parse_amount(raw)
            self.assertEqual(None if got is None else f"{got:.2f}", expected, raw)

    def test_date(self):
        cases = {
            "2026-03-04": date(2026, 3, 4),
            "2026/3/4": date(2026, 3, 4),
            "04.03.2026": date(2026, 3, 4),
            "03/04/2026": date(2026, 3, 4),
            "Mar 4, 2026": date(2026, 3, 4),
            "MARCH 4, 2026": date(2026, 3, 4),
            "4 Mar 2026": date(2026, 3, 4),
            "4 march 2026": date(2026, 3, 4),
            "Mar 4 2026": None,
            "2026-02-30": None,
            "": None,
        }
        for raw, expected in cases.items():
            self.assertEqual(clean.parse_date(raw), expected, raw)


class EndToEndTest(unittest.TestCase):
    def test_clean(self):
        source = (
            " Status , Order ID ,Amount,Customer Email,Currency,Order Date,Updated At,Notes\n"
            "# export line\n"
            'paid, b-1 ,"$1,000.50", X@Y.com ,,2026/3/10,2026-03-10T10:00:00Z,a\n'
            "refunded,B-1,5.00,x@y.com,USD,10 Mar 2026,2026-03-10 10:00:00,last tie wins\n"
            ", ,1,<email>,USD,2026-03-10,,no id\n"
            'shipped,B-2,"1.234,56",not-an-email,,04.03.2026,,\n'
            "paid,B-3,abc,z@y.com,,2026-03-04,,bad amount\n"
            "paid,B-4,12.34,z@y.com,,2026-02-30,,bad date\n"
            "lost,B-5,2.005,z@y.com,,5 March 2026,,\n"
            "paid,B-6,10,z@y.com,,2026-03-05,2026-03-05T00:00:00Z,older\n"
            "pending,B-6,20,z@y.com,,2026-03-05,2026-03-06T00:00:00Z,newer\n"
        )
        expected = [
            ["order_id", "customer_email", "amount", "currency", "order_date", "status"],
            ["B-2", "", "1234.56", "USD", "2026-03-04", "shipped"],
            ["B-5", "z@y.com", "2.01", "USD", "2026-03-05", "unknown"],
            ["B-6", "z@y.com", "20.00", "USD", "2026-03-05", "pending"],
            ["B-1", "x@y.com", "5.00", "USD", "2026-03-10", "refunded"],
        ]
        with tempfile.TemporaryDirectory() as folder:
            src = os.path.join(folder, "in.csv")
            dst = os.path.join(folder, "out.csv")
            with open(src, "w", encoding="utf-8-sig", newline="") as f:
                f.write(source)
            clean.clean(src, dst)
            with open(dst, encoding="utf-8", newline="") as f:
                raw = f.read()
            self.assertNotIn("\r", raw)
            self.assertEqual(list(csv.reader(raw.splitlines())), expected)


if __name__ == "__main__":
    unittest.main()
