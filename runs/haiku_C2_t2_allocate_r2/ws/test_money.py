import unittest
from decimal import Decimal
from fractions import Fraction

from money import allocate


class AllocateTest(unittest.TestCase):
    def test_examples(self):
        self.assertEqual(allocate(100, [1, 1, 1]), [34, 33, 33])
        self.assertEqual(allocate(100, [1, 2]), [33, 67])
        self.assertEqual(allocate(7, [0.1, 0.2, 0.7]), [1, 1, 5])
        self.assertEqual(allocate(0, [3, 5]), [0, 0])
        self.assertEqual(allocate(-5, [1, 1]), [-3, -2])

    def test_mixed_types_sum_exactly(self):
        shares = allocate(1000, [Fraction(1, 3), Decimal("2.5"), 0.7, 0])
        self.assertEqual(sum(shares), 1000)
        self.assertEqual(shares[3], 0)

    def test_does_not_modify_weights(self):
        weights = [1, 2]
        allocate(10, weights)
        self.assertEqual(weights, [1, 2])

    def test_errors(self):
        bad_calls = [
            (10, []),
            (10, [1, -1]),
            (10, [0, 0]),
            (10, [1, float("nan")]),
            (10, [1, float("inf")]),
            (10, [1, Decimal("NaN")]),
            (1.5, [1]),
            (True, [1]),
        ]
        for total, weights in bad_calls:
            with self.subTest(total=total, weights=weights):
                with self.assertRaises(ValueError):
                    allocate(total, weights)


if __name__ == "__main__":
    unittest.main()
