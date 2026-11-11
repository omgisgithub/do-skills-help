import math
import random
import unittest
from decimal import Decimal
from fractions import Fraction

from money import allocate


class SpecExamples(unittest.TestCase):
    def test_examples(self):
        self.assertEqual(allocate(100, [1, 1, 1]), [34, 33, 33])
        self.assertEqual(allocate(100, [1, 2]), [33, 67])
        self.assertEqual(allocate(7, [0.1, 0.2, 0.7]), [1, 1, 5])
        self.assertEqual(allocate(0, [3, 5]), [0, 0])
        self.assertEqual(allocate(-5, [1, 1]), [-3, -2])


class Rule1Sum(unittest.TestCase):
    def test_sum_and_length_always_match(self):
        rng = random.Random(1234)
        for _ in range(500):
            n = rng.randint(1, 6)
            weights = [rng.choice([0, 1, 2, 3.5, Fraction(1, 3), Decimal("0.7")]) for _ in range(n)]
            if all(w == 0 for w in weights):
                weights[0] = 1
            total = rng.randint(-1000, 1000)
            shares = allocate(total, weights)
            self.assertEqual(len(shares), n)
            self.assertEqual(sum(shares), total)
            self.assertTrue(all(isinstance(s, int) for s in shares))


class Rule2Types(unittest.TestCase):
    def test_decimal_and_fraction_weights(self):
        self.assertEqual(allocate(10, [Decimal("0.1"), Decimal("0.2")]), [3, 7])
        self.assertEqual(allocate(10, [Fraction(1, 3), Fraction(2, 3)]), [3, 7])

    def test_float_weight_is_exact_not_rounded(self):
        # 0.5 and 0.5 are exact binary fractions: a true tie, so index 0 gets the cent.
        self.assertEqual(allocate(1, [0.5, 0.5]), [1, 0])


class Rule3Ties(unittest.TestCase):
    def test_equal_weights_lower_index_wins(self):
        self.assertEqual(allocate(1, [1, 1]), [1, 0])

    def test_remainder_tie_larger_weight_wins(self):
        # shares are 0.5 and 1.5: equal remainders, weight 3 beats weight 1.
        self.assertEqual(allocate(2, [1, 3]), [0, 2])
        self.assertEqual(allocate(2, [3, 1]), [2, 0])

    def test_larger_remainder_beats_larger_weight(self):
        # shares 0.25/0.75 of 1 cent: index 1 has the larger remainder.
        self.assertEqual(allocate(1, [1, 3]), [0, 1])


class Rule4Zero(unittest.TestCase):
    def test_zero_weight_gets_zero(self):
        self.assertEqual(allocate(5, [0, 1, 1]), [0, 3, 2])
        self.assertEqual(allocate(1, [0, 0, 5]), [0, 0, 1])
        self.assertEqual(allocate(-7, [1, 0]), [-7, 0])


class Rule5Negative(unittest.TestCase):
    def test_negative_total_negates_shares(self):
        self.assertEqual(allocate(-1, [1, 1]), [-1, 0])
        self.assertEqual(allocate(-100, [1, 2]), [-33, -67])


class Rule6Errors(unittest.TestCase):
    def assertValueError(self, *args):
        with self.assertRaises(ValueError):
            allocate(*args)

    def test_empty_weights(self):
        self.assertValueError(10, [])

    def test_negative_weight(self):
        self.assertValueError(10, [1, -1])
        self.assertValueError(10, [Decimal("-0.5"), 1])
        self.assertValueError(10, [Fraction(-1, 2), 1])

    def test_all_zero_weights(self):
        self.assertValueError(10, [0, 0])
        self.assertValueError(10, [0.0, Decimal("0")])

    def test_nan_or_infinite_weight(self):
        self.assertValueError(10, [float("nan"), 1])
        self.assertValueError(10, [1, float("inf")])
        self.assertValueError(10, [-math.inf, 1])
        self.assertValueError(10, [Decimal("NaN"), 1])
        self.assertValueError(10, [Decimal("Infinity"), 1])
        self.assertValueError(10, [Decimal("sNaN"), 1])

    def test_total_must_be_int(self):
        self.assertValueError(10.0, [1, 1])
        self.assertValueError("10", [1, 1])
        self.assertValueError(None, [1, 1])
        self.assertValueError(Decimal("10"), [1, 1])

    def test_bool_total_rejected(self):
        self.assertValueError(True, [1, 1])
        self.assertValueError(False, [1, 1])


class Rule7NoMutation(unittest.TestCase):
    def test_weights_not_modified(self):
        weights = [0.1, 0.2, 0.7]
        before = list(weights)
        allocate(7, weights)
        self.assertEqual(weights, before)
        self.assertIs(type(weights), list)


if __name__ == "__main__":
    unittest.main()
