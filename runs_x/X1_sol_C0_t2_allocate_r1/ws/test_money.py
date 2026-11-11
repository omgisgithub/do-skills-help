"""Tests for exact largest-remainder allocation."""

import unittest
from decimal import Decimal, localcontext
from fractions import Fraction

from money import allocate


class AllocateTests(unittest.TestCase):
    def test_examples(self):
        for total, weights, expected in [
            (100, [1, 1, 1], [34, 33, 33]),
            (100, [1, 2], [33, 67]),
            (7, [0.1, 0.2, 0.7], [1, 1, 5]),
            (0, [3, 5], [0, 0]),
            (-5, [1, 1], [-3, -2]),
        ]:
            with self.subTest(total=total, weights=weights):
                self.assertEqual(allocate(total, weights), expected)

    def test_ties_use_weight_then_index(self):
        self.assertEqual(allocate(2, [1, 3]), [0, 2])
        self.assertEqual(allocate(2, [1, 1, 1]), [1, 1, 0])

    def test_float_remainders_are_exact(self):
        # These distinct binary floats would tie after rounded float division.
        self.assertEqual(allocate(1, [1.0, 1.0000000000000002]), [0, 1])

    def test_mixed_types_and_decimal_context(self):
        weights = [0, Fraction(1, 3), Decimal("0.5"), 1.0]
        original = weights.copy()
        with localcontext() as context:
            context.prec = 1
            self.assertEqual(allocate(11, weights), [0, 2, 3, 6])
        self.assertEqual(weights, original)

    def test_invalid_inputs_even_for_zero_total(self):
        invalid_weights = [
            [], [0, 0], [-1, 2], [float("nan")], [float("inf")],
            [float("-inf")], [Decimal("NaN")], [Decimal("sNaN")],
            [Decimal("Infinity")], [Decimal("-Infinity")],
        ]
        for weights in invalid_weights:
            with self.subTest(weights=weights):
                with self.assertRaises(ValueError):
                    allocate(0, weights)
        for total in [True, False, 1.0, Decimal(1), Fraction(1), "1", None]:
            with self.subTest(total=total):
                with self.assertRaises(ValueError):
                    allocate(total, [1])

    def test_conservation_zero_weights_and_sign_symmetry(self):
        weights = [0, Fraction(2, 7), Decimal("0.13"), 0.1, 5, 0]
        for total in [0, 1, 2, 17, 101, 10**100]:
            shares = allocate(total, weights)
            self.assertEqual(len(shares), len(weights))
            self.assertEqual(sum(shares), total)
            self.assertTrue(all(type(share) is int for share in shares))
            self.assertEqual(shares[0], 0)
            self.assertEqual(shares[-1], 0)
            self.assertEqual(allocate(-total, weights), [-s for s in shares])


if __name__ == "__main__":
    unittest.main()
