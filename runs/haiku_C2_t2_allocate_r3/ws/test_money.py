import unittest
from decimal import Decimal
from fractions import Fraction

from money import allocate


class AllocateTests(unittest.TestCase):
    def test_spec_examples(self):
        self.assertEqual(allocate(100, [1, 1, 1]), [34, 33, 33])
        self.assertEqual(allocate(100, [1, 2]), [33, 67])
        self.assertEqual(allocate(7, [0.1, 0.2, 0.7]), [1, 1, 5])
        self.assertEqual(allocate(0, [3, 5]), [0, 0])
        self.assertEqual(allocate(-5, [1, 1]), [-3, -2])

    def test_zero_weight_gets_zero(self):
        self.assertEqual(allocate(10, [0, 1, 0, 1]), [0, 5, 0, 5])

    def test_exact_types(self):
        self.assertEqual(allocate(10, [Fraction(1, 3), Decimal("2")]), [1, 9])

    def test_sum_is_exact(self):
        out = allocate(12345, [0.3, 0.3, 0.4])
        self.assertEqual(sum(out), 12345)

    def test_inputs_not_modified(self):
        weights = [1, 2]
        allocate(10, weights)
        self.assertEqual(weights, [1, 2])

    def test_errors(self):
        bad = [
            (1, []),
            (1, [1, -1]),
            (1, [0, 0]),
            (1, [float("nan")]),
            (1, [float("inf")]),
            (1, [Decimal("NaN")]),
            (1.0, [1]),
            (True, [1]),
        ]
        for total, weights in bad:
            with self.subTest(total=total, weights=weights):
                with self.assertRaises(ValueError):
                    allocate(total, weights)


if __name__ == "__main__":
    unittest.main()
