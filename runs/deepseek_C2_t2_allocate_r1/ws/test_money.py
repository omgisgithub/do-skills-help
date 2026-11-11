"""Tests for money.allocate. Run with: python3 -m unittest -v test_money"""

import unittest
from decimal import Decimal
from fractions import Fraction

from money import allocate


class AllocateTest(unittest.TestCase):
    def test_examples(self):
        self.assertEqual(allocate(100, [1, 1, 1]), [34, 33, 33])
        self.assertEqual(allocate(100, [1, 2]), [33, 67])
        self.assertEqual(allocate(7, [0.1, 0.2, 0.7]), [1, 1, 5])
        self.assertEqual(allocate(0, [3, 5]), [0, 0])
        self.assertEqual(allocate(-5, [1, 1]), [-3, -2])

    def test_always_sums_exactly(self):
        for total in (-101, -1, 0, 1, 101):
            for weights in ([1, 1, 1], [1, 2, 3], [1, 0, 4], [0.1, 0.2, 0.7]):
                self.assertEqual(sum(allocate(total, weights)), total)

    def test_ties(self):
        # Equal remainder and equal weight: lower index first.
        self.assertEqual(allocate(1, [1, 1, 1]), [1, 0, 0])
        self.assertEqual(allocate(2, [1, 1, 1]), [1, 1, 0])
        # Equal remainder, larger weight wins.
        self.assertEqual(allocate(2, [1, 3]), [0, 2])

    def test_zero_weight_gets_zero(self):
        self.assertEqual(allocate(1, [0, 1]), [0, 1])
        self.assertEqual(allocate(-1, [0, 1]), [0, -1])

    def test_exact_types(self):
        self.assertEqual(allocate(100, [Fraction(1, 3), Fraction(2, 3)]), [33, 67])
        self.assertEqual(
            allocate(7, [Decimal("0.1"), Decimal("0.2"), Decimal("0.7")]),
            [1, 1, 5],
        )

    def test_does_not_modify_weights(self):
        weights = [1, 2, 3]
        allocate(10, weights)
        self.assertEqual(weights, [1, 2, 3])

    def test_errors(self):
        bad_calls = [
            (10, []),
            (10, [1, -1]),
            (10, [0, 0]),
            (10, [float("nan"), 1]),
            (10, [float("inf"), 1]),
            (10, [float("-inf"), 1]),
            (10, [Decimal("NaN"), 1]),
            (10, [Decimal("Infinity"), 1]),
            (10.0, [1, 1]),
            (True, [1, 1]),
            ("10", [1, 1]),
        ]
        for total, weights in bad_calls:
            with self.subTest(total=total, weights=weights):
                with self.assertRaises(ValueError):
                    allocate(total, weights)


if __name__ == "__main__":
    unittest.main()
