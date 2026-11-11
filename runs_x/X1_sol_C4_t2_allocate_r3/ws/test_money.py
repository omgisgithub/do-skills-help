"""Test exact proportional allocation of cents."""

import unittest
from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import product

from money import allocate


class AllocateTests(unittest.TestCase):
    """Verify allocation rules and input validation."""

    def test_allocate_examples_return_expected_shares(self) -> None:
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

    def test_allocate_remainder_tie_favors_larger_weight(self) -> None:
        self.assertEqual(allocate(2, [1, 3]), [0, 2])

    def test_allocate_equal_weights_favor_lower_index(self) -> None:
        self.assertEqual(allocate(2, [1, 1, 1]), [1, 1, 0])

    def test_allocate_float_remainders_use_exact_binary_values(self) -> None:
        self.assertEqual(allocate(1, [0.3, 0.1 + 0.2]), [0, 1])
        self.assertEqual(allocate(1, [Fraction(1, 10), 0.1]), [0, 1])

    def test_allocate_mixed_types_ignore_decimal_context_precision(self) -> None:
        weights = [Decimal("0.1000000000000000000001"), Fraction(1, 10), 0, 0.0]

        with localcontext() as context:
            context.prec = 2
            result = allocate(1, weights)

        self.assertEqual(result, [1, 0, 0, 0])

    def test_allocate_large_values_remain_exact(self) -> None:
        total = 10**100 + 1

        self.assertEqual(allocate(total, [10**400, 10**400]), [(total + 1) // 2, total // 2])

    def test_allocate_zero_weights_receive_zero(self) -> None:
        for total in (-7, 0, 7):
            with self.subTest(total=total):
                self.assertEqual(allocate(total, [0, 3, 0]), [0, total, 0])

    def test_allocate_input_weights_remain_unchanged(self) -> None:
        weights = [Decimal("0.2"), Fraction(1, 3), 0.7, 2]
        original = weights.copy()

        allocate(19, weights)

        self.assertEqual(weights, original)

    def test_allocate_invalid_weights_raise_value_error_even_for_zero_total(self) -> None:
        cases = [
            [],
            [0, 0],
            [-1, 2],
            [Fraction(-1, 3), 1],
            [Decimal("-0.1"), 1],
            [float("nan")],
            [float("inf")],
            [float("-inf")],
            [Decimal("NaN")],
            [Decimal("sNaN")],
            [Decimal("Infinity")],
            [Decimal("-Infinity")],
        ]
        for weights in cases:
            with self.subTest(weights=weights):
                with self.assertRaises(ValueError):
                    allocate(0, weights)

    def test_allocate_invalid_totals_raise_value_error(self) -> None:
        for total in (True, False, 1.0, Decimal(1), Fraction(1), "1", None):
            with self.subTest(total=total):
                with self.assertRaises(ValueError):
                    allocate(total, [1])

    def test_allocate_small_integer_cases_preserve_invariants(self) -> None:
        for weights in product(range(3), repeat=3):
            if not any(weights):
                continue
            for total in range(10):
                with self.subTest(weights=weights, total=total):
                    result = allocate(total, list(weights))
                    self.assertEqual(len(result), len(weights))
                    self.assertEqual(sum(result), total)
                    self.assertTrue(all(type(share) is int for share in result))
                    self.assertEqual(allocate(-total, list(weights)), [-x for x in result])
                    for weight, share in zip(weights, result):
                        exact_share = Fraction(total * weight, sum(weights))
                        self.assertLessEqual(share - exact_share, 1)
                        self.assertGreater(share - exact_share, -1)
                        if weight == 0:
                            self.assertEqual(share, 0)
