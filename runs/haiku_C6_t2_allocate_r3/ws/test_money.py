import math
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


class Rules(unittest.TestCase):
    def test_sum_and_length(self):
        for total in (0, 1, 99, 12345, -777):
            out = allocate(total, [3, 7, 11])
            self.assertEqual(len(out), 3)
            self.assertEqual(sum(out), total)
            self.assertTrue(all(isinstance(x, int) for x in out))

    def test_weight_types(self):
        self.assertEqual(allocate(100, [Fraction(1, 2), Fraction(1, 2)]), [50, 50])
        self.assertEqual(allocate(100, [Decimal("1"), Decimal("2")]), [33, 67])
        self.assertEqual(allocate(100, [1.0, 2.0]), [33, 67])

    def test_float_is_exact(self):
        # exact tie (remainders 0.5 and 0.5) -> lower index gets the cent
        self.assertEqual(allocate(1, [0.5, 0.5]), [1, 0])

    def test_tie_larger_weight_then_lower_index(self):
        # equal weights and equal remainders (1/3 each) -> lower indexes first
        self.assertEqual(allocate(2, [1, 1, 1]), [1, 1, 0])
        # remainders equal (both 0.5): larger weight wins the cent
        self.assertEqual(allocate(1, [Fraction(1, 2), Fraction(3, 2)]), [0, 1])

    def test_zero_weight_gets_zero(self):
        self.assertEqual(allocate(10, [0, 1, 0, 1]), [0, 5, 0, 5])
        self.assertEqual(allocate(5, [0, 1]), [0, 5])

    def test_negative_total_negates(self):
        self.assertEqual(allocate(-100, [1, 1, 1]), [-34, -33, -33])
        self.assertEqual(allocate(-7, [0.1, 0.2, 0.7]), [-1, -1, -5])

    def test_input_not_modified(self):
        w = [1, 2, 3]
        allocate(10, w)
        self.assertEqual(w, [1, 2, 3])

    def test_big_totals(self):
        out = allocate(10**20 + 3, [1, 1, 1])
        self.assertEqual(sum(out), 10**20 + 3)


class Errors(unittest.TestCase):
    def assertRaisesValue(self, total, weights):
        with self.assertRaises(ValueError):
            allocate(total, weights)

    def test_empty_weights(self):
        self.assertRaisesValue(10, [])

    def test_negative_weight(self):
        self.assertRaisesValue(10, [1, -1])
        self.assertRaisesValue(10, [Decimal("-0.5"), 1])
        self.assertRaisesValue(10, [-0.5, 1])

    def test_all_zero(self):
        self.assertRaisesValue(10, [0, 0])
        self.assertRaisesValue(10, [0.0, Decimal("0")])

    def test_nan_inf(self):
        self.assertRaisesValue(10, [float("nan"), 1])
        self.assertRaisesValue(10, [1, float("inf")])
        self.assertRaisesValue(10, [float("-inf"), 1])
        self.assertRaisesValue(10, [Decimal("NaN"), 1])
        self.assertRaisesValue(10, [Decimal("sNaN"), 1])
        self.assertRaisesValue(10, [Decimal("Infinity"), 1])

    def test_total_not_int(self):
        self.assertRaisesValue(True, [1, 1])
        self.assertRaisesValue(False, [1, 1])
        self.assertRaisesValue(10.0, [1, 1])
        self.assertRaisesValue("10", [1, 1])
        self.assertRaisesValue(Decimal("10"), [1, 1])


if __name__ == "__main__":
    unittest.main()
