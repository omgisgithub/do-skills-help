"""Verify order cleaning with standard-library tests."""

import ast
import csv
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from clean import FIELDS, _amount, _order_date, _records, clean


class CleanTests(unittest.TestCase):
    """Exercise normalization and complete CSV exports."""

    def test_amount_formats_round_half_away_from_zero(self) -> None:
        cases = {
            "$1,234.50": "1234.50", "1.234,56 €": "1234.56",
            "(£1,000.005)": "-1000.01", "2.005": "2.01", "-2.005": "-2.01",
            "7,5": "75.00", "7,50": "7.50", "1,000": "1000.00",
            "1,234,56": "1234.56", " 1\u00a0234,50 ": "1234.50",
            ".5": "0.50", "12€34": "1234.00",
            "123456789012345678901234567890.125": "123456789012345678901234567890.13",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(_amount(value), expected)

    def test_amount_invalid_values_are_rejected(self) -> None:
        for value in ("", " ", "$", "NaN", "Infinity", "1e2", "abc", "1.2.3", "(1", "(-2)"):
            with self.subTest(value=value):
                self.assertIsNone(_amount(value))

    def test_date_supported_formats_are_normalized(self) -> None:
        for value in (
            "2026-03-04", "2026/3/4", "4.3.2026", "3/4/2026",
            "Mar 4, 2026", "MARCH 4, 2026", "4 mAr 2026", "4 March 2026",
        ):
            with self.subTest(value=value):
                self.assertEqual(_order_date(value), "2026-03-04")
        self.assertEqual(_order_date("2024-2-29"), "2024-02-29")

    def test_date_invalid_values_are_rejected(self) -> None:
        for value in ("", "2026-02-30", "2026-2-29", "Mar 4 2026", "4 Mars 2026", "13/1/2026"):
            with self.subTest(value=value):
                self.assertIsNone(_order_date(value))

    def test_records_comments_do_not_damage_multiline_fields(self) -> None:
        source = io.StringIO('\n# ignored\na, "first\n# retained\n\nlast"\n\n# ignored\nb,c\n')

        records = list(_records(source))

        self.assertEqual(records, [["a", "first\n# retained\n\nlast"], ["b", "c"]])

    def test_export_normalizes_deduplicates_and_sorts_valid_rows(self) -> None:
        headers = ["Status", " Order ID ", "Amount", "Customer Email", "Currency", "Order Date", "Updated At", "Extra"]
        rows = [
            ["paid", " a ", "1", " OLD@EXAMPLE.COM ", "", "2026-3-4", "", "ignored"],
            [" CANCELED ", "A", "2.005", " New@Example.COM ", "$", "4 Mar 2026", "2026-03-05T01:00:00Z"],
            ["shipped", "a", "3", "tie@example.com", " usd ", "4.3.2026", "2026-03-05 01:00:00"],
            ["paid", "A", "4", "old@example.com", "", "2026-3-4", "2026-03-04T01:00:00"],
            ["paid", "A", "bad", "", "", "2026-3-4", "2026-03-06T01:00:00"],
            ["paid", "A", "5", "", "", "2026-2-30", "2026-03-07T01:00:00"],
            ["wat", " B ", " € 1.234,56 ", "a@@b", "", "2026/3/4", ""],
            [" Refunded ", "C", "(12.50)", "@bad", " £ ", "March 3, 2026", ""],
            ["PAID", "D", "£3.10", "gina@example", "", "3/4/2026", ""],
            ["paid", "", "1", "a@b", "", "2026-3-4", ""],
            ["pending", "E", "1", "a@", "", "2026-3-5", ""],
            ["pending", "e", "2", "", "", "2026-3-5", ""],
        ]
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            source, destination = Path(directory) / "in.csv", Path(directory) / "out.csv"
            with source.open("w", encoding="utf-8-sig", newline="") as stream:
                stream.write("# preamble\n\n")
                writer = csv.writer(stream)
                writer.writerow(headers)
                writer.writerows(rows)

            clean(source, destination)
            result = destination.read_bytes()

        self.assertNotIn(b"\r", result)
        self.assertEqual(list(csv.reader(io.StringIO(result.decode()))), [
            list(FIELDS),
            ["C", "", "-12.50", "GBP", "2026-03-03", "refunded"],
            ["A", "tie@example.com", "3.00", "USD", "2026-03-04", "shipped"],
            ["B", "", "1234.56", "EUR", "2026-03-04", "unknown"],
            ["D", "gina@example", "3.10", "GBP", "2026-03-04", "paid"],
            ["E", "", "2.00", "USD", "2026-03-05", "pending"],
        ])

    def test_cli_sample_export_succeeds(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            output = Path(directory) / "cleaned.csv"

            subprocess.run([sys.executable, "clean.py", "orders_raw.csv", str(output)], check=True)

            with output.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
        self.assertEqual([row["order_id"] for row in rows], [
            "A-1001", "A-1002", "A-1003", "A-1006", "A-1007", "A-1008", "A-1010",
        ])
        self.assertEqual(rows[-1]["amount"], "-1000.01")

    def test_empty_export_writes_header(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            source, output = Path(directory) / "empty.csv", Path(directory) / "out.csv"
            source.write_text("# comment\n\n", encoding="utf-8")

            clean(source, output)

            self.assertEqual(output.read_text(), ",".join(FIELDS) + "\n")

    def test_source_uses_python39_syntax(self) -> None:
        ast.parse(Path("clean.py").read_text(), feature_version=(3, 9))


if __name__ == "__main__":
    unittest.main()
