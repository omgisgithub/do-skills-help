"""Tests for money.allocate."""

import unittest
from decimal import Decimal
from fractions import Fraction

from money import allocate


class AllocateExamplesTests(unittest.TestCase):
    """Examples taken directly from TASK.md."""

    def test_allocate_equal_weights_remainder_to_lower_index(self) -> None:
        self.assertEqual(allocate(100, [1, 1, 1]), [34, 33, 33])

    def test_allocate_integer_weights_proportional(self) -> None:
        self.assertEqual(allocate(100, [1, 2]), [33, 67])

    def test_allocate_float_weights_uses_exact_arithmetic(self) -> None:
        self.assertEqual(allocate(7, [0.1, 0.2, 0.7]), [1, 1, 5])

    def test_allocate_zero_total_gives_zero_shares(self) -> None:
        self.assertEqual(allocate(0, [3, 5]), [0, 0])

    def test_allocate_negative_total_negates_shares(self) -> None:
        self.assertEqual(allocate(-5, [1, 1]), [-3, -2])


class AllocateRulesTests(unittest.TestCase):
    """Rules from the spec beyond the examples."""

    def test_allocate_zero_weight_party_gets_nothing(self) -> None:
        self.assertEqual(allocate(10, [0, 1, 0]), [0, 10, 0])

    def test_allocate_remainder_tie_goes_to_larger_weight(self) -> None:
        # Exact shares are 0.5 and 1.5, so both remainders are 0.5. The larger weight wins.
        self.assertEqual(allocate(2, [1, 3]), [0, 2])

    def test_allocate_remainder_and_weight_tie_goes_to_lower_index(self) -> None:
        self.assertEqual(allocate(2, [1, 1, 1]), [1, 1, 0])

    def test_allocate_mixed_numeric_types_sums_exactly(self) -> None:
        self.assertEqual(allocate(5, [Fraction(1, 3), Decimal("0.5"), 2]), [1, 1, 3])

    def test_allocate_result_sums_to_total(self) -> None:
        weights = [0.3, 1.7, 2.2, 0.001]
        for total in range(-50, 51):
            with self.subTest(total=total):
                self.assertEqual(sum(allocate(total, weights)), total)

    def test_allocate_does_not_modify_weights(self) -> None:
        weights = [1, 2.5]

        allocate(9, weights)

        self.assertEqual(weights, [1, 2.5])

    def test_allocate_accepts_finite_large_decimal(self) -> None:
        self.assertEqual(allocate(10**6, [Decimal("1e400"), 1]), [1000000, 0])


class AllocateErrorTests(unittest.TestCase):
    """Invalid input raises ValueError (or TypeError for unsupported types)."""

    def test_allocate_empty_weights_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            allocate(1, [])

    def test_allocate_negative_weight_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            allocate(1, [-1, 2])

    def test_allocate_all_zero_weights_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            allocate(1, [0, 0])

    def test_allocate_nan_weight_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            allocate(1, [float("nan")])

    def test_allocate_infinite_weight_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            allocate(1, [float("inf")])

    def test_allocate_nan_decimal_weight_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            allocate(1, [Decimal("NaN")])

    def test_allocate_infinite_decimal_weight_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            allocate(1, [Decimal("-Infinity")])

    def test_allocate_bool_total_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            allocate(True, [1])

    def test_allocate_float_total_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            allocate(1.0, [1])

    def test_allocate_string_weight_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            allocate(1, ["a"])


if __name__ == "__main__":
    unittest.main()
