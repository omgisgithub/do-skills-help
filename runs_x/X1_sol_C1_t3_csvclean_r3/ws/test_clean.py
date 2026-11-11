import csv
import tempfile
import unittest
from pathlib import Path

from clean import FIELDS, clean, parse_amount, parse_date, parse_updated


class CleanerTests(unittest.TestCase):
    def test_amounts(self):
        examples = {
            "(12.50)": "-12.50", "2.005": "2.01", "-2.005": "-2.01",
            "$1,234.50": "1234.50", "1.234,56": "1234.56", "€ 7,5": "75.00",
            "1,000": "1000.00", "(1,000.005)": "-1000.01",
            "  £ 1 234,56  ": "1234.56", "12,50": "12.50", "99": "99.00",
            "123456789012345678901234567890.005": "123456789012345678901234567890.01",
        }
        for raw, expected in examples.items():
            with self.subTest(raw=raw):
                self.assertEqual(parse_amount(raw), expected)
        for raw in ("", "abc", "NaN", "Infinity", "1e3", "1.2.3", "(12", "12)", "--2", "(-2)"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_amount(raw)

    def test_dates(self):
        for raw in ("2026-03-04", "2026/03/04", "04.03.2026", "03/04/2026",
                    "Mar 4, 2026", "March 4, 2026", "4 Mar 2026", "4 March 2026",
                    "2026-3-4", "2026/3/4", "4.3.2026", "3/4/2026", "4 mArCh 2026"):
            with self.subTest(raw=raw):
                self.assertEqual(parse_date(raw), "2026-03-04")
        for raw in ("", "2026-02-30", "Mar 4 2026", "March 4 2026", "2026-3/4",
                    "2026-13-01", "4 Sept 2026", "4 March 26", "2026-03-04junk"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_date(raw)

    def test_updated(self):
        self.assertEqual(parse_updated("2026-03-04T10:00:00Z"), parse_updated("2026-03-04 10:00:00"))
        self.assertLess(parse_updated(""), parse_updated("2026-03-04T10:00:00"))

    def test_sample(self):
        root = Path(__file__).parent
        with tempfile.TemporaryDirectory(dir=root) as directory:
            output = Path(directory) / "output.csv"
            clean(root / "orders_raw.csv", output)
            self.assertEqual(output.read_text(), (
                "order_id,customer_email,amount,currency,order_date,status\n"
                "A-1001,alice@example.com,1300.00,USD,2026-03-04,refunded\n"
                "A-1002,bob@example.com,99.00,USD,2026-03-04,shipped\n"
                "A-1003,,1234.56,EUR,2026-03-04,cancelled\n"
                "A-1006,frank@example.com,75.00,EUR,2026-03-07,pending\n"
                "A-1007,gina@example,3.10,GBP,2026-03-09,unknown\n"
                "A-1008,hank@example.com,1000.00,GBP,2026-03-10,paid\n"
                "A-1010,jack@example.com,-1000.01,USD,2026-03-10,paid\n"
            ))

    def test_export(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            source = Path(directory) / "input.csv"
            output = Path(directory) / "output.csv"
            with source.open("w", encoding="utf-8-sig", newline="") as stream:
                stream.write("# ignored before header\n\n")
                writer = csv.writer(stream)
                writer.writerow(["Status", " Order ID", "Order Date", "Amount", "Customer Email", "Currency", "Updated At", "extra"])
                rows = [
                    [" PAID ", " a ", "2026-3-4", " $ 2.005 ", " Alice@Example.COM ", "", "2026-03-04T10:00:00Z"],
                    ["lost", "B", "2026-3-3", "£3.10", "gina@example", "", ""],
                    ["paid", "A", "2026-3-4", "4", "a@b", "eur", "2026-03-04 10:00:00"],
                    ["canceled", "a", "2026-3-4", "(12.50)", "a@@b", "$", "2026-03-04T11:00:00"],
                    ["paid", "a", "2026-02-30", "99", "a@b", "", "2026-03-05T11:00:00"],
                    ["paid", "a", "2026-3-4", "bad", "a@b", "", "2026-03-06T11:00:00"],
                    ["paid", " ", "2026-3-4", "5", "a@b", "", ""],
                    ["paid", "C", "2026-3-4", "", "a@b", "", ""],
                    ["SHIPPED", "D", "2026-3-4", "1", "@b", " £ ", ""],
                    ["refunded", "E", "2026-3-4", "1", "a@", " € ", ""],
                    ["pending", "F", "2026-3-4", "1", "ab", " gbp ", ""],
                    ["paid", "G", "2026-3-4", "1", "a@b", "", ""],
                    ["paid", "G", "2026-3-4", "2", "a@b", "", ""],
                ]
                writer.writerows(rows)
                stream.write("\n# ignored after rows\n")
            clean(source, output)
            self.assertNotIn(b"\r", output.read_bytes())
            with output.open(newline="") as stream:
                reader = csv.DictReader(stream)
                actual = list(reader)
                self.assertEqual(reader.fieldnames, list(FIELDS))
            self.assertEqual([r["order_id"] for r in actual], ["B", "A", "D", "E", "F", "G"])
            self.assertEqual(list(actual[0].values()), ["B", "gina@example", "3.10", "GBP", "2026-03-03", "unknown"])
            self.assertEqual(list(actual[1].values()), ["A", "", "-12.50", "USD", "2026-03-04", "cancelled"])
            self.assertEqual([r["currency"] for r in actual[2:]], ["GBP", "EUR", "GBP", "USD"])
            self.assertTrue(all(r["customer_email"] == "" for r in actual[2:5]))
            self.assertEqual(actual[-1]["amount"], "2.00")


if __name__ == "__main__":
    unittest.main()
