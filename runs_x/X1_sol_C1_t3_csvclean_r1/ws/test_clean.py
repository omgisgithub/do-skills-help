import csv
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from clean import FIELDS, parse_amount, parse_date, parse_updated_at


class CleanTests(unittest.TestCase):
    def test_amounts(self):
        for raw, expected in {
            "(12.50)": "-12.50", "2.005": "2.01", "-2.005": "-2.01",
            "$1,234.50": "1234.50", "1.234,56": "1234.56",
            "€ 7,5": "75.00", "1,000": "1000.00", "(1,000.005)": "-1000.01",
            " £ 1 234,50 ": "1234.50", "12$€£": "12.00", "1,234,56": "1234.56",
            "1.234": "1.23", "1,23": "1.23", "99": "99.00",
        }.items():
            with self.subTest(raw=raw):
                self.assertEqual(parse_amount(raw), expected)
        for raw in ("", " ", "$", "abc", "NaN", "Infinity", "1e3", "1.2.3", "(12", "12)"):
            with self.subTest(raw=raw):
                self.assertIsNone(parse_amount(raw))

    def test_dates(self):
        for raw in ("2026-03-04", "2026/03/04", "04.03.2026", "03/04/2026",
                    "Mar 4, 2026", "March 4, 2026", "4 Mar 2026", "4 March 2026",
                    "2026-3-4", "2026/3/4", "4.3.2026", "3/4/2026", "4 mArCh 2026"):
            with self.subTest(raw=raw):
                self.assertEqual(parse_date(raw), "2026-03-04")
        for raw in ("", "2026-02-30", "Mar 4 2026", "2026.03.04", "04-03-2026",
                    "2026-03/04", "4 Sept 2026", "March 4, 26", "March  4, 2026",
                    "2026-13-01", "2026-00-01", "0000-01-01"):
            with self.subTest(raw=raw):
                self.assertIsNone(parse_date(raw))

    def test_timestamps(self):
        expected = parse_updated_at("2026-03-04T10:00:00Z")
        for raw in ("2026-03-04T10:00:00", "2026-03-04 10:00:00", "2026-03-04 10:00:00Z"):
            self.assertEqual(parse_updated_at(raw), expected)
        self.assertLess(parse_updated_at(""), expected)

    def run_cli(self, directory, source):
        input_path = Path(directory) / "input.csv"
        output_path = Path(directory) / "output.csv"
        input_path.write_text(source, encoding="utf-8")
        subprocess.run([sys.executable, str(Path(__file__).with_name("clean.py")),
                        str(input_path), str(output_path)], check=True)
        self.assertNotIn(b"\r", output_path.read_bytes())
        with output_path.open(newline="", encoding="utf-8") as result:
            return list(csv.reader(result))

    def test_normalization_and_deduplication(self):
        source = "\ufeff# comment\n\n Status ,Order Date, Amount , Customer Email , Order ID ,Currency,Updated At,Extra\n"
        source += "PAID,2026-3-4,2.005, A@B , a-1 ,$,2026-03-04T10:00:00Z,x\n"
        source += "canceled,4 march 2026,(12.50),bad@@email,A-1, eur ,2026-03-04 10:00:00,x\n"
        source += "shipped,2026-3-4,10,old@b,A-1,GBP,,x\n"
        source += "paid,2026-3-4,invalid,new@b,A-1,USD,2026-03-05T00:00:00,x\n"
        source += "paid,2026-02-30,10,new@b,A-1,USD,2026-03-06T00:00:00,x\n"
        source += "pending,2026-3-3,€5,a@,a-2,,,x\n"
        source += "lost,2026-3-4,£3.10,gina@example,b-1,,,x\n"
        source += "refunded,2026-3-4,1,@b,b-2,,,x\n"
        source += "paid,2026-3-4,1,a@b,  ,USD,,x\n"
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            self.assertEqual(self.run_cli(directory, source), [list(FIELDS),
                ["A-2", "", "5.00", "EUR", "2026-03-03", "pending"],
                ["A-1", "", "-12.50", "EUR", "2026-03-04", "cancelled"],
                ["B-1", "gina@example", "3.10", "GBP", "2026-03-04", "unknown"],
                ["B-2", "", "1.00", "USD", "2026-03-04", "refunded"]])

    def test_sample(self):
        source = Path(__file__).with_name("orders_raw.csv").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            self.assertEqual(self.run_cli(directory, source), [list(FIELDS),
                ["A-1001", "alice@example.com", "1300.00", "USD", "2026-03-04", "refunded"],
                ["A-1002", "bob@example.com", "99.00", "USD", "2026-03-04", "shipped"],
                ["A-1003", "", "1234.56", "EUR", "2026-03-04", "cancelled"],
                ["A-1006", "frank@example.com", "75.00", "EUR", "2026-03-07", "pending"],
                ["A-1007", "gina@example", "3.10", "GBP", "2026-03-09", "unknown"],
                ["A-1008", "hank@example.com", "1000.00", "GBP", "2026-03-10", "paid"],
                ["A-1010", "jack@example.com", "-1000.01", "USD", "2026-03-10", "paid"]])


if __name__ == "__main__":
    unittest.main()
