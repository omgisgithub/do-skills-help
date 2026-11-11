"""Specification checks for exact invoice allocation."""

import unittest
from decimal import Decimal, localcontext
from fractions import Fraction

from money import allocate


class AllocateTests(unittest.TestCase):
    def test_spec_examples(self):
        assert allocate(100, [1, 1, 1]) == [34, 33, 33]
        assert allocate(100, [1, 2]) == [33, 67]
        assert allocate(7, [0.1, 0.2, 0.7]) == [1, 1, 5]
        assert allocate(0, [3, 5]) == [0, 0]
        assert allocate(-5, [1, 1]) == [-3, -2]

    def test_remainder_then_weight_then_index(self):
        self.assertEqual(allocate(2, [1, 2]), [1, 1])
        self.assertEqual(allocate(2, [1, 3]), [0, 2])
        self.assertEqual(allocate(1, [3, 3, 3]), [1, 0, 0])

    def test_exact_weight_types(self):
        self.assertEqual(allocate(3, [1, 1.0, Fraction(1), Decimal(1)]),
                         [1, 1, 1, 0])
        # Converting through decimal strings would turn this into a tie.
        self.assertEqual(allocate(1, [Fraction(1, 10), 0.1]), [0, 1])
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(allocate(1, [Decimal('1.001'), Decimal('1.002')]),
                             [0, 1])

    def test_zero_weights_and_no_mutation(self):
        weights = [0, Decimal('2.5'), Fraction(0), 0.0]
        original = weights.copy()
        self.assertEqual(allocate(7, weights), [0, 7, 0, 0])
        self.assertEqual(weights, original)

    def test_sum_length_types_and_negative_symmetry(self):
        weights = [0, 1, Fraction(2, 3), 0.1, Decimal('0.7')]
        for total in [0, 1, 2, 7, 100, 10**100]:
            positive = allocate(total, weights)
            self.assertEqual(sum(positive), total)
            self.assertEqual(len(positive), len(weights))
            self.assertTrue(all(type(share) is int for share in positive))
            self.assertEqual(allocate(-total, weights), [-s for s in positive])

    def test_invalid_weights_even_for_zero_total(self):
        invalid = [[], [0, 0], [-1, 2], [Fraction(-1, 2)],
                   [Decimal('-0.1')], [float('nan')], [float('inf')],
                   [float('-inf')], [Decimal('NaN')], [Decimal('sNaN')],
                   [Decimal('Infinity')], [Decimal('-Infinity')], ['1'],
                   [1 + 0j], [None]]
        for weights in invalid:
            for total in [0, 1]:
                with self.subTest(weights=weights, total=total):
                    with self.assertRaises(ValueError):
                        allocate(total, weights)

    def test_invalid_total(self):
        for total in [True, False, 1.0, Decimal(1), Fraction(1), '1', None]:
            with self.subTest(total=total):
                with self.assertRaises(ValueError):
                    allocate(total, [1])


if __name__ == '__main__':
    unittest.main()
