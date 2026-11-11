"""Test exact proportional allocation."""

import unittest
from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import product

from money import allocate


class AllocateTests(unittest.TestCase):
    """Verify allocation rules and invalid inputs."""

    def test_allocate_examples_return_expected_shares(self) -> None:
        cases = [
            (100, [1, 1, 1], [34, 33, 33]),
            (100, [1, 2], [33, 67]),
            (7, [0.1, 0.2, 0.7], [1, 1, 5]),
            (0, [3, 5], [0, 0]),
            (-5, [1, 1], [-3, -2]),
            (5, [0, 1, 0], [0, 5, 0]),
        ]
        for total, weights, expected in cases:
            with self.subTest(total=total, weights=weights):
                self.assertEqual(allocate(total, weights), expected)

    def test_allocate_equal_remainders_prefer_weight_then_index(self) -> None:
        self.assertEqual(allocate(2, [1, 3]), [0, 2])
        self.assertEqual(allocate(1, [1, 1, 1]), [1, 0, 0])

    def test_allocate_float_remainders_use_exact_binary_values(self) -> None:
        self.assertEqual(allocate(1, [0.3, 0.1 + 0.2]), [0, 1])

    def test_allocate_mixed_weights_preserve_precision_and_input(self) -> None:
        weights = [1, 0.5, Fraction(1, 2), Decimal("0.5"), Decimal("0")]
        original = weights.copy()

        with localcontext() as context:
            context.prec = 2
            shares = allocate(10**30 + 1, weights)

        self.assertEqual(shares, [4 * 10**29 + 1, 2 * 10**29, 2 * 10**29, 2 * 10**29, 0])
        self.assertEqual(weights, original)

    def test_allocate_invalid_totals_raise_value_error(self) -> None:
        for total in (True, False, 1.0, "1", None, Fraction(1), Decimal(1)):
            with self.subTest(total=total), self.assertRaises(ValueError):
                allocate(total, [1])

    def test_allocate_invalid_weights_raise_even_for_zero_total(self) -> None:
        cases = [
            [], [0, 0], [-1, 2], [Fraction(-1, 2)], [Decimal("-0.1")],
            [float("nan")], [float("inf")], [float("-inf")],
            [Decimal("NaN")], [Decimal("sNaN")],
            [Decimal("Infinity")], [Decimal("-Infinity")],
        ]
        for weights in cases:
            with self.subTest(weights=weights), self.assertRaises(ValueError):
                allocate(0, weights)

    def test_allocate_small_inputs_preserve_sum_floor_and_sign(self) -> None:
        for weights in product(range(4), repeat=3):
            if not any(weights):
                continue
            for total in range(15):
                shares = allocate(total, list(weights))

                self.assertEqual(sum(shares), total)
                self.assertEqual(allocate(-total, list(weights)), [-share for share in shares])
                for share, weight in zip(shares, weights):
                    exact = Fraction(total * weight, sum(weights))
                    self.assertIs(type(share), int)
                    self.assertIn(share, (exact // 1, -(-exact // 1)))
                    if weight == 0:
                        self.assertEqual(share, 0)


if __name__ == "__main__":
    unittest.main()
