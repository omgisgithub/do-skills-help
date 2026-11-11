# Implement `allocate` in `money.py`

We split invoices between cost centres. Implement `allocate(total_cents, weights)` in `money.py`
exactly to this spec. Python 3.9, standard library only.

## Spec

`allocate(total_cents: int, weights: list) -> list[int]`

1. Returns a list of ints, same length as `weights`, that sums to **exactly** `total_cents`.
2. Each share is proportional to its weight. Weights may be `int`, `float`, `fractions.Fraction`
   or `decimal.Decimal`. Use **exact** arithmetic (convert floats with `Fraction(x)`; do not let
   float rounding decide a tie).
3. Method (largest remainder): each party first gets the floor of its exact share. The leftover
   cents are handed out one each, to the parties with the largest fractional remainder.
   Ties in remainder go to the party with the **larger weight**; if weights are also equal, to the
   **lower index**.
4. A party with weight 0 always gets 0.
5. Negative `total_cents`: allocate `abs(total_cents)` as above, then negate every share
   (so `allocate(-5, [1, 1])` is `[-3, -2]`).
6. Errors — raise `ValueError` when: `weights` is empty; any weight is negative; all weights
   are zero; any weight is NaN or infinite; `total_cents` is not an `int` (a `bool` is not an int
   here).
7. Must not modify the `weights` list passed in.

## Examples

```
allocate(100, [1, 1, 1])        -> [34, 33, 33]
allocate(100, [1, 2])           -> [33, 67]
allocate(7, [0.1, 0.2, 0.7])    -> [1, 1, 5]
allocate(0, [3, 5])             -> [0, 0]
allocate(-5, [1, 1])            -> [-3, -2]
```
