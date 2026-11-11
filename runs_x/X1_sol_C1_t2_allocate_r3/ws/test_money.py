"""Specification checks for invoice allocation."""

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

    def test_remainder_and_tie_order(self):
        self.assertEqual(allocate(2, [1, 3]), [0, 2])
        self.assertEqual(allocate(1, [1, 1, 1]), [1, 0, 0])
        self.assertEqual(allocate(3, [1, 2, 4]), [0, 1, 2])
        self.assertEqual(allocate(1, [1.0, 1.0000000000000002]), [0, 1])

    def test_exact_mixed_types(self):
        weights = [1, 0.5, Fraction(1, 4), Decimal("0.25")]
        original = weights[:]
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(allocate(100, weights), [50, 25, 13, 12])
        self.assertEqual(weights, original)
        self.assertEqual(allocate(1, [Decimal("0.1"), 0.1]), [0, 1])

    def test_zero_weights_and_large_totals(self):
        self.assertEqual(allocate(2, [0, 1, 0, 1]), [0, 1, 0, 1])
        self.assertEqual(allocate(-1, [0, 1, 0]), [0, -1, 0])
        total = 10**100 + 1
        self.assertEqual(allocate(total, [0, 1]), [0, total])

    def test_invalid_totals(self):
        for total in [True, False, 1.0, Fraction(1), Decimal(1), "1", None]:
            with self.subTest(total=total), self.assertRaises(ValueError):
                allocate(total, [1])

    def test_invalid_weights_even_for_zero_total(self):
        invalid = [[], [0, 0], [-1, 2], [-0.1, 1],
                   [Fraction(-1, 3), 1], [Decimal("-0.1"), 1],
                   [float("nan")], [float("inf")], [float("-inf")],
                   [Decimal("NaN")], [Decimal("sNaN")],
                   [Decimal("Infinity")], [Decimal("-Infinity")], ["1"]]
        for weights in invalid:
            for total in (0, 5):
                with self.subTest(weights=weights, total=total):
                    with self.assertRaises(ValueError):
                        allocate(total, weights)

    def test_invariants(self):
        for total in range(-20, 21):
            for weights in ([0, 1, 2, 3], [1, 1, 1],
                            [Fraction(1, 7), Decimal("0.3"), 0.1]):
                with self.subTest(total=total, weights=weights):
                    result = allocate(total, weights)
                    self.assertEqual(len(result), len(weights))
                    self.assertEqual(sum(result), total)
                    self.assertTrue(all(type(share) is int for share in result))
                    self.assertEqual(result, [-share for share in
                                             allocate(-total, weights)])
                    denominator = sum(map(Fraction, weights))
                    for weight, share in zip(weights, result):
                        exact = abs(total) * Fraction(weight) / denominator
                        floor = exact.numerator // exact.denominator
                        self.assertIn(abs(share), (floor, floor + 1))
                        if weight == 0:
                            self.assertEqual(share, 0)


if __name__ == "__main__":
    unittest.main()
