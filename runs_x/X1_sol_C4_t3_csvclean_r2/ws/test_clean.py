"""Test order cleaning with the standard library unittest runner."""

import csv
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from clean import OUTPUT_FIELDS, _parse_amount, _parse_date, clean_orders


class CleanOrdersTests(unittest.TestCase):
    """Check field rules and complete CSV exports."""

    def test_amount_formats_round_half_away_from_zero(self) -> None:
        cases = {
            "$1,234.50": "1234.50", "1.234,56€": "1234.56", "£ 7,5": "75.00",
            "1,000": "1000.00", "1,23": "1.23", "2.005": "2.01", "-2.005": "-2.01",
            "(1,000.005)": "-1000.01", "(12.50)": "-12.50", "1 234,50": "1234.50",
            "1,234,567.89": "1234567.89", "1.234.567,89": "1234567.89",
            "99999999999999999999999999999.995": "100000000000000000000000000000.00",
            ".5": "0.50", "+12": "12.00", "0": "0.00",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(_parse_amount(raw), expected)

    def test_amount_invalid_values_are_rejected(self) -> None:
        for raw in ("", " ", "$", "NaN", "Infinity", "1.2.3", "abc", "(12", "12)", "(-2)"):
            with self.subTest(raw=raw):
                self.assertIsNone(_parse_amount(raw))

    def test_date_supported_formats_are_normalized(self) -> None:
        for raw in (
            "2026-03-04", "2026/3/4", "2026-3-4", "4.3.2026", "3/4/2026",
            "Mar 4, 2026", "mARCH 4, 2026", "4 MAR 2026", "4 March 2026",
        ):
            with self.subTest(raw=raw):
                self.assertEqual(_parse_date(raw), "2026-03-04")
        self.assertEqual(_parse_date("2024-02-29"), "2024-02-29")

    def test_date_invalid_values_are_rejected(self) -> None:
        for raw in ("", "2026-02-30", "2026-02-29", "Mar 4 2026", "4 Mars 2026", "2026/3-4"):
            with self.subTest(raw=raw):
                self.assertIsNone(_parse_date(raw))

    def _clean_export(self, text: str) -> tuple[list[dict[str, str]], bytes]:
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            source = Path(directory) / "input.csv"
            target = Path(directory) / "output.csv"
            source.write_text(text, encoding="utf-8")

            clean_orders(source, target)

            result = target.read_bytes()
        return list(csv.DictReader(io.StringIO(result.decode("utf-8")))), result

    def test_export_reordered_headers_bom_comments_and_field_rules(self) -> None:
        text = (
            '\ufeff# export\n\n Status ,Amount, Order ID ,Order Date,Customer Email,Currency,Extra\n'
            ' Canceled ,"€ 1.234,56", b ,4 MAR 2026, <email> ,,ignored\n'
            'lost,£3.1,a,2026/3/4,invalid,,ignored\n'
            'PAID,1,c,2026-3-3,a@@b,$,ignored\n'
            'pending,1,d,2026-3-5,@b,gbp,ignored\n'
            'shipped,1,e,2026-3-5,a@,,ignored\n'
            'refunded,2,f,2026-3-5,a@b,eur,ignored\n'
        )

        rows, data = self._clean_export(text)

        self.assertEqual([row["order_id"] for row in rows], ["C", "A", "B", "D", "E", "F"])
        self.assertEqual(rows[2], dict(zip(OUTPUT_FIELDS, (
            "B", "<email>", "1234.56", "EUR", "2026-03-04", "cancelled"
        ))))
        self.assertEqual(rows[1]["status"], "unknown")
        self.assertEqual([row["customer_email"] for row in rows[:2]], ["", ""])
        self.assertEqual([row["currency"] for row in rows], ["USD", "GBP", "EUR", "GBP", "USD", "EUR"])
        self.assertEqual(rows[3]["customer_email"], "")
        self.assertEqual(rows[4]["customer_email"], "")
        self.assertNotIn(b"\r", data)
        self.assertTrue(data.startswith((",".join(OUTPUT_FIELDS) + "\n").encode()))

    def test_deduplication_uses_latest_valid_row_and_later_ties(self) -> None:
        text = "order_id,amount,order_date,updated_at\n" + "\n".join((
            "a,1,2026-3-4,", "A,2,2026-3-4,2026-03-05T00:00:00Z",
            "a,3,2026-3-4,2026-03-04 00:00:00", "a,4,2026-3-4,2026-03-05 00:00:00",
            "a,bad,2026-3-4,2026-03-06T00:00:00Z", "a,5,2026-2-30,2026-03-07T00:00:00Z",
            ",6,2026-3-4,", "b,7,2026-3-4,", "B,8,2026-3-4,", "a,9,2026-3-4,",
        ))

        rows, _ = self._clean_export(text)

        self.assertEqual([(row["order_id"], row["amount"]) for row in rows], [("A", "4.00"), ("B", "8.00")])

    def test_empty_input_writes_header_only(self) -> None:
        rows, data = self._clean_export("# nothing\n\n")

        self.assertEqual(rows, [])
        self.assertEqual(data.decode(), ",".join(OUTPUT_FIELDS) + "\n")

    def test_cli_sample_produces_expected_orders(self) -> None:
        root = Path(__file__).parent
        with tempfile.TemporaryDirectory(dir=root) as directory:
            target = Path(directory) / "output.csv"

            subprocess.run(
                [sys.executable, str(root / "clean.py"), str(root / "orders_raw.csv"), str(target)],
                check=True, capture_output=True,
            )

            with target.open(newline="", encoding="utf-8") as source:
                rows = list(csv.DictReader(source))
        self.assertEqual([row["order_id"] for row in rows], [
            "A-1001", "A-1002", "A-1003", "A-1006", "A-1007", "A-1008", "A-1010"
        ])
        self.assertEqual(rows[0]["amount"], "1300.00")
        self.assertEqual(rows[-1]["amount"], "-1000.01")


if __name__ == "__main__":
    unittest.main()
