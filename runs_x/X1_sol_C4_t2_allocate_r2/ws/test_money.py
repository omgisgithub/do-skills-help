"""Test exact invoice allocation."""

import unittest
from decimal import Decimal, localcontext
from fractions import Fraction

from money import allocate


class AllocateTests(unittest.TestCase):
    """Check allocation rules and invalid inputs."""

    def test_allocate_examples_match_spec(self) -> None:
        cases = [
            (100, [1, 1, 1], [34, 33, 33]),
            (100, [1, 2], [33, 67]),
            (7, [0.1, 0.2, 0.7], [1, 1, 5]),
            (0, [3, 5], [0, 0]),
            (-5, [1, 1], [-3, -2]),
        ]
        for total, weights, expected in cases:
            with self.subTest(total=total, weights=weights):
                self.assertEqual(allocate(total, weights), expected)

    def test_allocate_equal_remainders_favor_larger_weight(self) -> None:
        self.assertEqual(allocate(2, [1, 3]), [0, 2])

    def test_allocate_equal_weights_favor_lower_index(self) -> None:
        self.assertEqual(allocate(2, [1, 1, 1]), [1, 1, 0])

    def test_allocate_zero_weights_receive_nothing(self) -> None:
        self.assertEqual(allocate(2, [0, 1, 0, 1, 0, 1]), [0, 1, 0, 1, 0, 0])

    def test_allocate_float_values_keep_binary_precision(self) -> None:
        self.assertEqual(allocate(1, [Fraction(1, 10), 0.1]), [0, 1])

    def test_allocate_near_ties_keep_exact_remainders(self) -> None:
        self.assertEqual(allocate(1, [2**60, 2**60 + 1]), [0, 1])

    def test_allocate_mixed_types_preserves_weights(self) -> None:
        weights = [1, 0.5, Fraction(1, 2), Decimal("0.5")]
        original = weights.copy()

        shares = allocate(7, weights)

        self.assertEqual(shares, [3, 2, 1, 1])
        self.assertEqual(weights, original)
        self.assertTrue(all(type(share) is int for share in shares))

    def test_allocate_decimals_ignore_context_precision(self) -> None:
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(allocate(1, [Decimal("1"), Decimal("1.00001")]), [0, 1])

    def test_allocate_large_total_preserves_sum_and_sign(self) -> None:
        total = 10**100 + 1

        positive = allocate(total, [1, 2, 3])
        negative = allocate(-total, [1, 2, 3])

        self.assertEqual(sum(positive), total)
        self.assertEqual(negative, [-share for share in positive])

    def test_allocate_invalid_weights_raise_value_error(self) -> None:
        cases = [
            [], [0, 0], [-1, 2], [Fraction(-1, 3), 1], [Decimal("-0.1"), 1],
            [float("nan")], [float("inf")], [float("-inf")],
            [Decimal("NaN")], [Decimal("sNaN")],
            [Decimal("Infinity")], [Decimal("-Infinity")],
        ]
        for weights in cases:
            for total in (0, 5, -5):
                with self.subTest(weights=weights, total=total):
                    with self.assertRaises(ValueError):
                        allocate(total, weights)

    def test_allocate_invalid_totals_raise_value_error(self) -> None:
        for total in (True, False, 1.0, Fraction(1), Decimal(1), "1", None):
            with self.subTest(total=total):
                with self.assertRaises(ValueError):
                    allocate(total, [1])


if __name__ == "__main__":
    unittest.main()
