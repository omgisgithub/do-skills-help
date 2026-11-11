import decimal
import fractions
import unittest

from money import allocate


class AllocateTest(unittest.TestCase):
    def test_examples(self):
        self.assertEqual(allocate(100, [1, 1, 1]), [34, 33, 33])
        self.assertEqual(allocate(100, [1, 2]), [33, 67])
        self.assertEqual(allocate(7, [0.1, 0.2, 0.7]), [1, 1, 5])
        self.assertEqual(allocate(0, [3, 5]), [0, 0])
        self.assertEqual(allocate(-5, [1, 1]), [-3, -2])

    def test_zero_weight_gets_zero_and_types_mix(self):
        self.assertEqual(allocate(10, [0, decimal.Decimal("1"), fractions.Fraction(1, 2)]), [0, 7, 3])

    def test_input_not_modified(self):
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
            (1, [decimal.Decimal("NaN")]),
            (1.0, [1]),
            (True, [1]),
        ]
        for total, weights in bad:
            with self.subTest(total=total, weights=weights):
                with self.assertRaises(ValueError):
                    allocate(total, weights)


if __name__ == "__main__":
    unittest.main()
