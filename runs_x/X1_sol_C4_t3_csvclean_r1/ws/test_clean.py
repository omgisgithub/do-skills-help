"""Verify the standalone order export cleaner."""

from __future__ import annotations

import csv
import io
import tempfile
import unittest
from pathlib import Path

from clean import OUTPUT_FIELDS, _amount, _clean_row, _csv_rows, _order_date, clean


class CleanTests(unittest.TestCase):
    """Exercise field rules and complete export processing."""

    def test_amount_formats_round_half_away_from_zero(self) -> None:
        cases = {
            "$1,234.50": "1234.50", "1.234,56 €": "1234.56", "£ 1 234,50": "1234.50",
            "(12.50)": "-12.50", "(1,000.005)": "-1000.01", "2.005": "2.01",
            "-2.005": "-2.01", "7,5": "75.00", "1,000": "1000.00",
            "1,234,56": "1234.56", ".5": "0.50", "0": "0.00",
            "123456789012345678901234567890.005": "123456789012345678901234567890.01",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(_amount(raw), expected)

    def test_amount_invalid_values_are_rejected(self) -> None:
        for raw in ("", " ", "$", "NaN", "Infinity", "1e3", "abc", "1.2.3", "(12", "(-2)"):
            with self.subTest(raw=raw):
                self.assertIsNone(_amount(raw))

    def test_order_date_accepts_all_documented_formats(self) -> None:
        for raw in (
            "2026-03-04", "2026-3-4", "2026/3/4", "4.3.2026", "3/4/2026",
            "Mar 4, 2026", "mArCh 4, 2026", "4 MAR 2026", "4 March 2026",
        ):
            with self.subTest(raw=raw):
                self.assertEqual(_order_date(raw), "2026-03-04")

    def test_order_date_rejects_invalid_and_unlisted_forms(self) -> None:
        for raw in ("", "2026-02-30", "2025-02-29", "Mar 4 2026", "4 Foo 2026", "2026-3/4"):
            with self.subTest(raw=raw):
                self.assertIsNone(_order_date(raw))
        self.assertEqual(_order_date("2024-2-29"), "2024-02-29")

    def test_clean_row_normalizes_email_currency_and_status(self) -> None:
        base = {"order_id": "a", "amount": "€1", "order_date": "2026-1-1"}
        for email, expected in (("USER@EXAMPLE", "user@example"), ("@x", ""), ("x@", ""), ("a@@b", "")):
            with self.subTest(email=email):
                row = _clean_row(dict(base, customer_email=email, status="CANCELED"))

                self.assertIsNotNone(row)
                if row is not None:
                    self.assertEqual(row["customer_email"], expected)
                    self.assertEqual(row["currency"], "EUR")
                    self.assertEqual(row["status"], "cancelled")
        for currency, expected in (("$", "USD"), ("£", "GBP"), ("eur", "EUR")):
            with self.subTest(currency=currency):
                row = _clean_row(dict(base, currency=currency))
                if row is not None:
                    self.assertEqual(row["currency"], expected)

    def test_csv_rows_preserves_multiline_fields_and_ignores_comments(self) -> None:
        source = io.StringIO('# ignored\n\na,b\n"hello\n# kept\n\nworld",x\n# ignored\n')

        rows = list(_csv_rows(source))

        self.assertEqual(rows, [["a", "b"], ["hello\n# kept\n\nworld", "x"]])

    def test_clean_export_deduplicates_valid_rows_and_sorts(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            source = Path(temporary) / "input.csv"
            destination = Path(temporary) / "output.csv"
            source.write_text(
                '\ufeff# comment\n\n Status ,Amount,Order Date,Order ID,Updated At,Customer Email,Currency,Extra\n'
                ' paid ,1,2026-3-4, b ,2026-03-04T01:00:00Z, U@EXAMPLE ,,ignored\n'
                'shipped,2,2026-3-4,B,2026-03-04 01:00:00,u@example,,\n'
                'paid,3,2026-3-4,b,2026-03-03T01:00:00Z,u@example,,\n'
                'paid,bad,2026-3-4,b,2026-03-05T01:00:00Z,u@example,,\n'
                'paid,4,2026-2-30,b,2026-03-06T01:00:00Z,u@example,,\n'
                'lost,2.005,2026-3-4,a,,bad@@email,,\n'
                'paid,7,2026-3-3,z,,,,\n'
                'refunded,8,2026-3-3,Z,,,,\n'
                'paid,1,2026-3-3, ,,,,\n', encoding="utf-8",
            )

            clean(source, destination)

            raw = destination.read_bytes()
            self.assertNotIn(b"\r", raw)
            rows = list(csv.reader(io.StringIO(raw.decode("utf-8"))))
            self.assertEqual(rows, [
                list(OUTPUT_FIELDS),
                ["Z", "", "8.00", "USD", "2026-03-03", "refunded"],
                ["A", "", "2.01", "USD", "2026-03-04", "unknown"],
                ["B", "u@example", "2.00", "USD", "2026-03-04", "shipped"],
            ])

    def test_clean_empty_export_writes_header(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            source = Path(temporary) / "input.csv"
            destination = Path(temporary) / "output.csv"
            source.write_text("# no orders\n\n", encoding="utf-8")

            clean(source, destination)

            self.assertEqual(destination.read_text(), ",".join(OUTPUT_FIELDS) + "\n")


if __name__ == "__main__":
    unittest.main()
