"""Tests for :func:`money.allocate`."""

import random
import unittest
from decimal import Decimal
from fractions import Fraction

from money import allocate


class AllocateSpecExamplesTest(unittest.TestCase):
    """Cover the examples from TASK.md."""

    def test_allocate_thirds_splits_evenly(self) -> None:
        self.assertEqual(allocate(100, [1, 1, 1]), [34, 33, 33])

    def test_allocate_one_to_two(self) -> None:
        self.assertEqual(allocate(100, [1, 2]), [33, 67])

    def test_allocate_float_weights_are_exact(self) -> None:
        self.assertEqual(allocate(7, [0.1, 0.2, 0.7]), [1, 1, 5])

    def test_allocate_zero_total(self) -> None:
        self.assertEqual(allocate(0, [3, 5]), [0, 0])

    def test_allocate_negative_total_is_negated(self) -> None:
        self.assertEqual(allocate(-5, [1, 1]), [-3, -2])


class AllocateRoundingTest(unittest.TestCase):
    """Cover largest-remainder tie-breaking."""

    def test_allocate_tie_goes_to_larger_weight(self) -> None:
        self.assertEqual(allocate(2, [1, 3]), [0, 2])

    def test_allocate_equal_weights_tie_goes_to_lower_index(self) -> None:
        self.assertEqual(allocate(1, [1, 1]), [1, 0])

    def test_allocate_zero_weight_receives_nothing(self) -> None:
        self.assertEqual(allocate(1, [0, 1, 0, 1]), [0, 1, 0, 0])

    def test_allocate_fraction_weights(self) -> None:
        self.assertEqual(allocate(10, [Fraction(1, 3), Fraction(2, 3)]), [3, 7])

    def test_allocate_decimal_weights(self) -> None:
        self.assertEqual(allocate(10, [Decimal("1"), Decimal("2")]), [3, 7])

    def test_allocate_sums_exactly_for_many_inputs(self) -> None:
        rng = random.Random(0)
        for _ in range(500):
            size = rng.randint(1, 8)
            weights = [rng.randint(0, 20) for _ in range(size)]
            if not any(weights):
                continue
            total = rng.randint(-10**6, 10**6)
            shares = allocate(total, weights)
            self.assertEqual(sum(shares), total)
            self.assertEqual(len(shares), size)
            for share, weight in zip(shares, weights):
                if weight == 0:
                    self.assertEqual(share, 0)


class AllocateValidationTest(unittest.TestCase):
    """Cover the documented error cases."""

    def test_allocate_empty_weights_raises(self) -> None:
        with self.assertRaises(ValueError):
            allocate(10, [])

    def test_allocate_negative_weight_raises(self) -> None:
        with self.assertRaises(ValueError):
            allocate(10, [1, -1])

    def test_allocate_all_zero_weights_raises(self) -> None:
        with self.assertRaises(ValueError):
            allocate(10, [0, 0])

    def test_allocate_nan_weight_raises(self) -> None:
        with self.assertRaises(ValueError):
            allocate(10, [1, float("nan")])
        with self.assertRaises(ValueError):
            allocate(10, [1, Decimal("NaN")])

    def test_allocate_infinite_weight_raises(self) -> None:
        with self.assertRaises(ValueError):
            allocate(10, [1, float("inf")])
        with self.assertRaises(ValueError):
            allocate(10, [1, Decimal("Infinity")])

    def test_allocate_non_int_total_raises(self) -> None:
        with self.assertRaises(ValueError):
            allocate(10.0, [1])
        with self.assertRaises(ValueError):
            allocate("10", [1])

    def test_allocate_bool_total_raises(self) -> None:
        with self.assertRaises(ValueError):
            allocate(True, [1])

    def test_allocate_does_not_modify_weights(self) -> None:
        weights = [1, 2, 3]
        allocate(10, weights)
        self.assertEqual(weights, [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
