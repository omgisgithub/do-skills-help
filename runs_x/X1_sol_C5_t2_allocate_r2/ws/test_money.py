import unittest
from decimal import Decimal, localcontext
from fractions import Fraction

from money import allocate


class AllocateTests(unittest.TestCase):
    def test_examples(self):
        cases = [
            (100, [1, 1, 1], [34, 33, 33]),
            (100, [1, 2], [33, 67]),
            (7, [0.1, 0.2, 0.7], [1, 1, 5]),
            (0, [3, 5], [0, 0]),
            (-5, [1, 1], [-3, -2]),
        ]
        for total, weights, expected in cases:
            with self.subTest(total=total, weights=weights):
                self.assertEqual(allocate(total, weights), expected)

    def test_remainder_ties_prefer_larger_weight(self):
        self.assertEqual(allocate(2, [1, 3]), [0, 2])

    def test_equal_weights_prefer_lower_index(self):
        self.assertEqual(allocate(2, [1, 1, 1]), [1, 1, 0])

    def test_floats_keep_exact_binary_value(self):
        self.assertEqual(allocate(1, [Fraction(1, 10), 0.1]), [0, 1])

    def test_mixed_types_and_decimal_context(self):
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(
                allocate(10, [1, 0.5, Fraction(1, 4), Decimal('0.75')]),
                [4, 2, 1, 3],
            )
            self.assertEqual(allocate(1, [Decimal('1'), Decimal('1.01')]), [0, 1])

    def test_zero_weights_never_receive_cents(self):
        for total, expected in [(1, [0, 1, 0]), (-1, [0, -1, 0]), (0, [0, 0, 0])]:
            with self.subTest(total=total):
                self.assertEqual(allocate(total, [0, 5, 0]), expected)

    def test_large_total_is_exact(self):
        self.assertEqual(
            allocate(10**100 + 1, [1, 1]),
            [5 * 10**99 + 1, 5 * 10**99],
        )

    def test_does_not_modify_weights_and_returns_ints(self):
        weights = [Decimal('0.3'), Fraction(1, 5), 0, 0.5]
        original = weights.copy()
        result = allocate(17, weights)
        self.assertEqual(weights, original)
        self.assertEqual(len(result), len(weights))
        self.assertEqual(sum(result), 17)
        self.assertTrue(all(type(share) is int for share in result))

    def test_invalid_totals(self):
        for total in [True, False, 1.0, Decimal('1'), Fraction(1), '1', None]:
            with self.subTest(total=total):
                with self.assertRaises(ValueError):
                    allocate(total, [1])

    def test_invalid_weights_even_for_zero_total(self):
        invalid = [
            [], [0, 0], [-1, 2], [Fraction(-1, 3), 1],
            [Decimal('-0.1'), 1], [-0.1, 1],
        ]
        for value in [float('nan'), float('inf'), float('-inf'),
                      Decimal('NaN'), Decimal('sNaN'),
                      Decimal('Infinity'), Decimal('-Infinity')]:
            invalid.append([1, value])
        for total in [0, 5]:
            for weights in invalid:
                with self.subTest(total=total, weights=weights):
                    with self.assertRaises(ValueError):
                        allocate(total, weights)


if __name__ == '__main__':
    unittest.main()
