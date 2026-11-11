import unittest
from decimal import Decimal, localcontext
from fractions import Fraction

from money import allocate


class AllocateTests(unittest.TestCase):
    def test_examples(self):
        for total, weights, expected in [
            (100, [1, 1, 1], [34, 33, 33]),
            (100, [1, 2], [33, 67]),
            (7, [0.1, 0.2, 0.7], [1, 1, 5]),
            (0, [3, 5], [0, 0]),
            (-5, [1, 1], [-3, -2]),
        ]:
            with self.subTest(total=total, weights=weights):
                self.assertEqual(allocate(total, weights), expected)

    def test_remainder_ties_favor_larger_weight_then_lower_index(self):
        self.assertEqual(allocate(2, [1, 3]), [0, 2])
        self.assertEqual(allocate(2, [1, 1, 1]), [1, 1, 0])

    def test_zero_weights_never_receive_cents(self):
        self.assertEqual(allocate(2, [0, 1, 0, 1, 0]), [0, 1, 0, 1, 0])
        self.assertEqual(allocate(-1, [0, 0, 3]), [0, 0, -1])

    def test_float_keeps_its_exact_binary_value(self):
        self.assertEqual(allocate(1, [Fraction(1, 10), 0.1]), [0, 1])

    def test_mixed_numeric_weights_and_decimal_context(self):
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(
                allocate(10, [1, 0.5, Fraction(1, 4), Decimal('0.75')]),
                [4, 2, 1, 3],
            )
            self.assertEqual(
                allocate(1, [Decimal('1'), Decimal('1.00000000000000000001')]),
                [0, 1],
            )

    def test_huge_totals_and_weights_stay_exact(self):
        self.assertEqual(
            allocate(2**54 + 1, [1.0, 1.0]),
            [2**53 + 1, 2**53],
        )
        self.assertEqual(allocate(3, [10**400, 10**400]), [2, 1])

    def test_invalid_totals_raise_value_error(self):
        for total in [True, False, 1.0, Decimal('1'), Fraction(1), '1', None]:
            with self.subTest(total=total):
                with self.assertRaises(ValueError):
                    allocate(total, [1])

    def test_invalid_weights_raise_value_error_even_for_zero_total(self):
        for weights in [
            [], [0, 0], [-1, 2], [Fraction(-1, 3), 1],
            [Decimal('-0.1'), 1], [float('nan')], [float('inf')],
            [float('-inf')], [Decimal('NaN')], [Decimal('sNaN')],
            [Decimal('Infinity')], [Decimal('-Infinity')],
        ]:
            for total in [0, 5]:
                with self.subTest(total=total, weights=weights):
                    with self.assertRaises(ValueError):
                        allocate(total, weights)

    def test_input_is_unchanged_and_results_are_ints(self):
        weights = [Decimal('0.5'), Fraction(3, 2), 0.0]
        original = weights[:]
        result = allocate(7, weights)
        self.assertEqual(weights, original)
        self.assertEqual(result, [2, 5, 0])
        self.assertTrue(all(type(share) is int for share in result))


if __name__ == '__main__':
    unittest.main()
