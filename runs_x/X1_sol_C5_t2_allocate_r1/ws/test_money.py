"""Behavioral tests for exact invoice allocation."""

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

    def test_remainder_ties_favor_larger_weight_then_lower_index(self):
        self.assertEqual(allocate(2, [1, 3]), [0, 2])
        self.assertEqual(allocate(2, [1, 1, 1]), [1, 1, 0])

    def test_exact_float_values_decide_remainders(self):
        # The float 0.1 is slightly greater than the exact rational 1/10.
        self.assertEqual(allocate(1, [Fraction(1, 10), 0.1]), [0, 1])

    def test_large_weights_do_not_round_to_a_tie(self):
        self.assertEqual(allocate(1, [2**54, 2**54 + 1]), [0, 1])

    def test_mixed_types_are_exact_even_with_low_decimal_precision(self):
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(
                allocate(10, [1, 0.5, Fraction(1, 4), Decimal('0.75')]),
                [4, 2, 1, 3],
            )

    def test_zero_weights_never_receive_cents(self):
        for total in (0, 1, -1, 10**50):
            with self.subTest(total=total):
                self.assertEqual(allocate(total, [0, 2, Decimal('-0')]),
                                 [0, total, 0])

    def test_invalid_inputs_raise_value_error_even_for_zero_total(self):
        invalid_weights = [
            [], [0, 0], [-1, 2], [Fraction(-1, 3), 1],
            [Decimal('-0.1'), 1], [float('nan')], [float('inf')],
            [float('-inf')], [Decimal('NaN')], [Decimal('sNaN')],
            [Decimal('Infinity')], [Decimal('-Infinity')],
        ]
        for weights in invalid_weights:
            with self.subTest(weights=weights):
                with self.assertRaises(ValueError):
                    allocate(0, weights)
        for total in (True, False, 1.0, Fraction(1), Decimal(1), '1', None):
            with self.subTest(total=total):
                with self.assertRaises(ValueError):
                    allocate(total, [1])

    def test_conservation_sign_integer_results_and_input_preservation(self):
        weights = [0, Fraction(1, 3), Decimal('1.25'), 0.1, 7]
        original = weights.copy()
        for total in range(-30, 31):
            shares = allocate(total, weights)
            self.assertEqual(sum(shares), total)
            self.assertEqual(len(shares), len(weights))
            self.assertTrue(all(type(share) is int for share in shares))
            self.assertEqual(shares, [-x for x in allocate(-total, weights)])
        self.assertEqual(weights, original)


if __name__ == '__main__':
    unittest.main()
