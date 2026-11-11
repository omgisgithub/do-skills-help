"""FIFO inventory costing.

Money is handled as `decimal.Decimal`. Unit costs may be given as `Decimal`, `int` or `str`
(e.g. "2.335"); floats are rejected with `TypeError`.
"""
from datetime import date
from decimal import Context, Decimal, MAX_EMAX, MIN_EMIN, ROUND_HALF_UP, localcontext


def _cost_total(terms, rounded=False):
    """Sum (quantity, cost) terms without losing digits to context precision."""
    terms = list(terms)
    if not terms:
        return Decimal("0.00") if rounded else Decimal(0)
    # Allow for every product's integer digits, the smallest fractional place,
    # and carry digits from summing all the products. Include cents for quantize.
    highest = max(cost.adjusted() + len(str(qty)) for qty, cost in terms)
    lowest = min(-2, min(cost.as_tuple().exponent for _, cost in terms))
    precision = max(28, highest - lowest + len(str(len(terms))) + 2)
    with localcontext(Context(prec=precision, Emax=MAX_EMAX, Emin=MIN_EMIN)):
        total = sum((qty * cost for qty, cost in terms), Decimal(0))
        if rounded:
            return total.quantize(Decimal("0.01"), ROUND_HALF_UP)
        return total


class Inventory:
    """Stock per SKU, kept as lots (purchases). Each lot is (date, qty, unit_cost)."""

    def __init__(self):
        self._lots = {}  # sku -> list of [when, qty, unit_cost]

    def buy(self, sku, qty, unit_cost, when):
        """Record a purchase of `qty` units (int > 0) at `unit_cost` each on date `when`.

        Purchases may be recorded out of order (a late invoice for an earlier date). Lots are
        always consumed oldest `when` first; lots with the same date in the order they were
        recorded. Raises ValueError for qty <= 0 or a negative unit cost.
        """
        if not isinstance(qty, int):
            raise TypeError("qty must be an integer")
        if qty <= 0:
            raise ValueError("qty must be positive")
        if isinstance(unit_cost, float):
            raise TypeError("use Decimal or str for money")
        cost = Decimal(unit_cost)
        if cost < 0:
            raise ValueError("negative cost")
        self._lots.setdefault(sku, []).append([when, qty, cost])
        self._lots[sku].sort(key=lambda lot: lot[0])

    def sell(self, sku, qty, when):
        """Sell `qty` units (int > 0) and return the COGS as a Decimal with 2 decimals.

        COGS is the exact sum of qty x unit_cost over the units taken from each lot, rounded
        once at the end to cents, half up (2.345 -> 2.35). Only lots dated on or before
        `when` can be sold from. If there are not enough such units, raise ValueError and
        leave the inventory completely unchanged. Fully used lots disappear.
        """
        if not isinstance(qty, int):
            raise TypeError("qty must be an integer")
        if qty <= 0:
            raise ValueError("qty must be positive")
        lots = self._lots.get(sku, [])
        if sum(lot[1] for lot in lots if lot[0] <= when) < qty:
            raise ValueError("not enough stock")
        terms = []
        updated = []
        remaining = qty
        for lot in lots:
            if remaining == 0 or lot[0] > when:
                updated.append(lot)
                continue
            take = min(remaining, lot[1])
            terms.append((take, lot[2]))
            if lot[1] > take:
                updated.append([lot[0], lot[1] - take, lot[2]])
            remaining -= take
        cogs = _cost_total(terms, rounded=True)
        self._lots[sku] = updated
        return cogs

    def on_hand(self, sku):
        """Units of `sku` in stock (0 for an unknown SKU)."""
        return sum(l[1] for l in self._lots.get(sku, []))

    def value(self, sku=None):
        """Exact remaining cost of stock (not rounded): one SKU, or all SKUs if sku is None."""
        skus = [sku] if sku is not None else list(self._lots)
        return _cost_total((l[1], l[2]) for s in skus for l in self._lots.get(s, []))

    def lots(self, sku):
        """A list of (when, qty, unit_cost) tuples for `sku`, in the order they will be consumed.
        Changing the returned list must not change the inventory."""
        return [tuple(lot) for lot in self._lots.get(sku, [])]
