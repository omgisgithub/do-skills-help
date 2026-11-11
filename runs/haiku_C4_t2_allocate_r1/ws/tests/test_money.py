"""Tests for money.allocate."""

import unittest
from decimal import Decimal
from fractions import Fraction

from money import allocate


class AllocateExamplesTest(unittest.TestCase):
    """The examples from TASK.md."""

    def test_allocate_three_equal_weights_gives_leftover_to_lowest_index(self) -> None:
        self.assertEqual(allocate(100, [1, 1, 1]), [34, 33, 33])

    def test_allocate_two_weights_gives_leftover_to_larger_remainder(self) -> None:
        self.assertEqual(allocate(100, [1, 2]), [33, 67])

    def test_allocate_float_weights_uses_exact_arithmetic(self) -> None:
        self.assertEqual(allocate(7, [0.1, 0.2, 0.7]), [1, 1, 5])

    def test_allocate_zero_total_gives_all_zero_shares(self) -> None:
        self.assertEqual(allocate(0, [3, 5]), [0, 0])

    def test_allocate_negative_total_negates_shares(self) -> None:
        self.assertEqual(allocate(-5, [1, 1]), [-3, -2])


class AllocateRulesTest(unittest.TestCase):
    """Rules 1 to 7 of the spec."""

    def test_allocate_shares_sum_to_total(self) -> None:
        shares = allocate(1000, [Fraction(1, 3), 0.3, Decimal("0.7")])

        self.assertEqual(sum(shares), 1000)

    def test_allocate_result_length_matches_weights(self) -> None:
        self.assertEqual(len(allocate(10, [1, 2, 3, 4])), 4)

    def test_allocate_accepts_fraction_and_decimal_weights(self) -> None:
        self.assertEqual(allocate(10, [Fraction(1, 4), Fraction(3, 4)]), [2, 8])
        self.assertEqual(allocate(10, [Decimal("0.25"), Decimal("0.75")]), [2, 8])

    def test_allocate_tie_in_remainder_prefers_larger_weight(self) -> None:
        # Exact shares are 0.5 and 1.5, so both remainders are 0.5.
        self.assertEqual(allocate(2, [1, 3]), [0, 2])

    def test_allocate_larger_remainder_wins_over_larger_weight(self) -> None:
        # Exact shares are 2/3 and 1/3; the larger remainder wins despite the smaller weight.
        self.assertEqual(allocate(1, [2, 1]), [1, 0])

    def test_allocate_equal_remainder_and_weight_prefers_lower_index(self) -> None:
        self.assertEqual(allocate(2, [1, 1, 1]), [1, 1, 0])

    def test_allocate_zero_weight_party_always_gets_zero(self) -> None:
        self.assertEqual(allocate(10, [0, 1, 0, 1]), [0, 5, 0, 5])

    def test_allocate_zero_weight_party_gets_zero_when_leftover_exists(self) -> None:
        shares = allocate(1, [0, 1, 1])

        self.assertEqual(shares[0], 0)
        self.assertEqual(sum(shares), 1)

    def test_allocate_does_not_modify_weights(self) -> None:
        weights = [1, 2, 3]

        allocate(10, weights)

        self.assertEqual(weights, [1, 2, 3])

    def test_allocate_negative_total_with_leftover_negates_each_share(self) -> None:
        self.assertEqual(allocate(-100, [1, 1, 1]), [-34, -33, -33])


class AllocateErrorsTest(unittest.TestCase):
    """Rule 6 of the spec."""

    def test_allocate_empty_weights_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            allocate(10, [])

    def test_allocate_negative_weight_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            allocate(10, [1, -1])

    def test_allocate_all_zero_weights_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            allocate(10, [0, 0.0, Decimal(0)])

    def test_allocate_nan_weight_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            allocate(10, [1, float("nan")])

    def test_allocate_infinite_weight_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            allocate(10, [1, float("inf")])

    def test_allocate_nan_decimal_weight_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            allocate(10, [Decimal("NaN"), 1])

    def test_allocate_infinite_decimal_weight_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            allocate(10, [Decimal("Infinity"), 1])

    def test_allocate_float_total_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            allocate(10.0, [1, 1])

    def test_allocate_bool_total_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            allocate(True, [1, 1])


if __name__ == "__main__":
    unittest.main()
