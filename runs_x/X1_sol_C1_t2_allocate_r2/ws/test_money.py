"""Checks for the allocation rules in TASK.md."""

import unittest
from decimal import Decimal
from fractions import Fraction

from money import allocate


class AllocateTests(unittest.TestCase):
    def test_spec_examples(self):
        assert allocate(100, [1, 1, 1]) == [34, 33, 33]
        assert allocate(100, [1, 2]) == [33, 67]
        assert allocate(7, [0.1, 0.2, 0.7]) == [1, 1, 5]
        assert allocate(0, [3, 5]) == [0, 0]
        assert allocate(-5, [1, 1]) == [-3, -2]

    def test_remainders_and_ties(self):
        self.assertEqual(allocate(2, [1, 3]), [0, 2])
        self.assertEqual(allocate(2, [3, 1]), [2, 0])
        self.assertEqual(allocate(1, [1, 1, 1]), [1, 0, 0])
        self.assertEqual(allocate(1, [1, 2]), [0, 1])
        self.assertEqual(allocate(-2, [1, 3]), [0, -2])

    def test_exact_numeric_types(self):
        self.assertEqual(allocate(1, [Fraction(1, 10), 0.1]), [0, 1])
        self.assertEqual(allocate(1, [Decimal('0.1'), Fraction(1, 10)]), [1, 0])
        self.assertEqual(allocate(6, [1, 0.5, Fraction(1, 2), Decimal('1')]),
                         [2, 1, 1, 2])
        self.assertEqual(allocate(1, [Decimal('1'), Decimal('1.00000000000000000000000000001')]),
                         [0, 1])

    def test_zero_weights(self):
        self.assertEqual(allocate(1, [0, 0, 1]), [0, 0, 1])
        self.assertEqual(allocate(-7, [0, 2, 0]), [0, -7, 0])
        self.assertEqual(allocate(0, [0, 1]), [0, 0])

    def test_invalid_weights(self):
        invalid = [[], [0, 0], [-1, 2], [-0.5, 1],
                   [Fraction(-1, 3), 1], [Decimal('-0.1'), 1],
                   ['1'], [None]]
        invalid += [[value, 1] for value in (
            float('nan'), float('inf'), float('-inf'),
            Decimal('NaN'), Decimal('sNaN'), Decimal('Infinity'),
            Decimal('-Infinity'))]
        for weights in invalid:
            for total in (0, 1, -1):
                with self.subTest(weights=weights, total=total):
                    with self.assertRaises(ValueError):
                        allocate(total, weights)

    def test_invalid_totals(self):
        for total in (True, False, 1.0, Fraction(1), Decimal('1'), '1', None):
            with self.subTest(total=total):
                with self.assertRaises(ValueError):
                    allocate(total, [1])

    def test_invariants_and_input_preservation(self):
        weights = [0, Decimal('0.3'), Fraction(2, 7), 0.1, 2]
        original = weights.copy()
        exact = [Fraction(weight) for weight in weights]
        for total in (-10**50, -17, -1, 0, 1, 17, 10**50):
            shares = allocate(total, weights)
            self.assertEqual(len(shares), len(weights))
            self.assertEqual(sum(shares), total)
            self.assertTrue(all(type(share) is int for share in shares))
            self.assertEqual(shares[0], 0)
            self.assertEqual(weights, original)
            for share, weight in zip(shares, exact):
                quota = abs(total) * weight / sum(exact)
                floor = quota.numerator // quota.denominator
                self.assertIn(abs(share), (floor, floor + 1))


if __name__ == '__main__':
    unittest.main()
