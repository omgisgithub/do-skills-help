import datetime as dt
import os
import tempfile
import unittest
from decimal import Decimal

import clean


def run(lines):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "in.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("\n".join(lines) + "\n")
        return clean.clean_rows(clean.read_rows(path))


HDR = "order_id,customer_email,amount,currency,order_date,status,updated_at"


class Amount(unittest.TestCase):
    def amt(self, raw):
        r = clean.parse_amount(raw)
        return None if r is None else str(r[0])

    def test_examples(self):
        self.assertEqual(self.amt("$1,234.50"), "1234.50")
        self.assertEqual(self.amt("1.234,56"), "1234.56")
        self.assertEqual(self.amt("(12.50)"), "-12.50")
        self.assertEqual(self.amt("2.005"), "2.01")
        self.assertEqual(self.amt("1,000"), "1000.00")
        self.assertEqual(self.amt("1,234,56"), "1234.56")
        self.assertEqual(self.amt("(1,000.005)"), "-1000.01")
        self.assertEqual(self.amt("€ 7,5"), "75.00")
        self.assertEqual(self.amt("99"), "99.00")

    def test_must_fail(self):
        for raw in ["", "$", "abc", "(12.50", "12.50)", "1.2.3", "1,5.5.5", "12a", "--5", "(-5)"]:
            self.assertIsNone(clean.parse_amount(raw), raw)

    def test_symbol(self):
        self.assertEqual(clean.parse_amount("£3.10")[1], "£")
        self.assertIsNone(clean.parse_amount("3.10")[1])


class Date(unittest.TestCase):
    def test_accepted(self):
        d = dt.date(2026, 3, 4)
        for raw in ["2026-03-04", "2026/03/04", "04.03.2026", "03/04/2026",
                    "Mar 4, 2026", "March 4, 2026", "4 Mar 2026", "4 March 2026",
                    "mar 4, 2026", "2026/3/4", " 4 march 2026 "]:
            self.assertEqual(clean.parse_date(raw), d, raw)

    def test_rejected(self):
        for raw in ["2026-02-30", "", "Mar 4 2026", "March. 4, 2026", "Sept 4, 2026",
                    "2026-03-04T10:00:00", "13/01/2026", "2026-13-01", "04-03-2026", "4 Mar, 2026"]:
            self.assertIsNone(clean.parse_date(raw), raw)


class Rows(unittest.TestCase):
    def test_sample_file(self):
        rows = clean.read_rows(os.path.join(os.path.dirname(__file__), "orders_raw.csv"))
        ids = [r["order_id"] for r in clean.clean_rows(rows)]
        self.assertEqual(ids, ["A-1001", "A-1002", "A-1003", "A-1006", "A-1007", "A-1008", "A-1010"])

    def test_bom_comments_blank_and_column_order(self):
        out = run(["﻿# comment", "", " Status , Order ID ,Amount,Order Date,Currency,Customer Email",
                   " paid , a-1 ,1,2026-01-01,, X@Y.com "])
        self.assertEqual(out[0]["order_id"], "A-1")
        self.assertEqual(out[0]["customer_email"], "x@y.com")
        self.assertEqual(out[0]["currency"], "USD")

    def test_email_rules(self):
        base = "a-1,{},1,USD,2026-01-01,paid,"
        for raw, want in [("<email>", "<email>"), ("a@@b", ""), ("@b", ""), ("a@", ""), ("nomail", "")]:
            self.assertEqual(run([HDR, base.format(raw)])[0]["customer_email"], want, raw)

    def test_status_rules(self):
        for raw, want in [("Canceled", "cancelled"), ("SHIPPED", "shipped"), ("lost", "unknown"), ("", "unknown")]:
            self.assertEqual(run([HDR, f"a,x@y.z,1,USD,2026-01-01,{raw},"])[0]["status"], want, raw)

    def test_drops(self):
        self.assertEqual(run([HDR, " ,x@y.z,1,USD,2026-01-01,paid,"]), [])
        self.assertEqual(run([HDR, "a,x@y.z,,USD,2026-01-01,paid,"]), [])
        self.assertEqual(run([HDR, "a,x@y.z,abc,USD,2026-01-01,paid,"]), [])
        self.assertEqual(run([HDR, "a,x@y.z,1,USD,2026-02-30,paid,"]), [])

    def test_dedup_latest_then_later_on_tie(self):
        out = run([HDR,
                   "a,x@y.z,1,USD,2026-01-01,paid,2026-01-02T00:00:00Z",
                   "a,x@y.z,2,USD,2026-01-01,paid,2026-01-03 00:00:00",
                   "b,x@y.z,3,USD,2026-01-01,paid,2026-01-05",
                   "b,x@y.z,4,USD,2026-01-01,paid,2026-01-05",
                   "c,x@y.z,9,USD,2026-01-01,paid,2026-01-09T00:00:00",
                   "c,x@y.z,8,USD,2026-01-01,paid,"])
        self.assertEqual({r["order_id"]: r["amount"] for r in out},
                         {"A": "2.00", "B": "4.00", "C": "9.00"})

    def test_dropped_rows_do_not_dedup(self):
        out = run([HDR, "a,x@y.z,1,USD,2026-01-01,paid,2026-01-01",
                   "a,x@y.z,oops,USD,2026-01-01,paid,2026-06-01"])
        self.assertEqual(out[0]["amount"], "1.00")

    def test_sort(self):
        out = run([HDR, "b,x@y.z,1,USD,2026-01-02,paid,", "c,x@y.z,1,USD,2026-01-01,paid,",
                   "a,x@y.z,1,USD,2026-01-02,paid,"])
        self.assertEqual([r["order_id"] for r in out], ["C", "A", "B"])

    def test_negative_zero(self):
        self.assertEqual(clean.parse_amount("(0.00)")[0], Decimal("0.00"))
        self.assertEqual(str(clean.parse_amount("(0.00)")[0]), "0.00")


if __name__ == "__main__":
    unittest.main()
