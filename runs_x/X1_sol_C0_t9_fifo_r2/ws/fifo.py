"""FIFO inventory costing.

Money is handled as `decimal.Decimal`. Unit costs may be given as `Decimal`, `int` or `str`
(e.g. "2.335"); floats are rejected with `TypeError`.
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, localcontext


def _exact_cost(lots):
    """Sum (quantity, cost) pairs without losing digits to Decimal's context."""
    lots = list(lots)
    if not lots:
        return Decimal(0)
    exponent = min(cost.as_tuple().exponent for qty, cost in lots)
    precision = max(
        len(cost.as_tuple().digits) + len(str(qty))
        + cost.as_tuple().exponent - exponent
        for qty, cost in lots
    ) + len(str(len(lots)))
    with localcontext() as context:
        context.prec = max(1, precision)
        return sum((qty * cost for qty, cost in lots), Decimal(0))


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
        if not cost.is_finite() or cost < 0:
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
        taken = []
        remaining = qty
        for lot in lots:
            if remaining == 0:
                break
            if lot[0] > when:
                continue
            take = min(remaining, lot[1])
            taken.append((lot, take))
            remaining -= take
        cogs = _exact_cost((take, lot[2]) for lot, take in taken)
        with localcontext() as context:
            context.prec = max(1, len(cogs.as_tuple().digits), cogs.adjusted() + 4)
            result = cogs.quantize(Decimal("0.01"), ROUND_HALF_UP)
        for lot, take in taken:
            lot[1] -= take
        self._lots[sku] = [lot for lot in lots if lot[1] > 0]
        return result

    def on_hand(self, sku):
        """Units of `sku` in stock (0 for an unknown SKU)."""
        return sum(l[1] for l in self._lots.get(sku, []))

    def value(self, sku=None):
        """Exact remaining cost of stock (not rounded): one SKU, or all SKUs if sku is None."""
        skus = [sku] if sku is not None else list(self._lots)
        return _exact_cost((l[1], l[2]) for s in skus for l in self._lots.get(s, []))

    def lots(self, sku):
        """A list of (when, qty, unit_cost) tuples for `sku`, in the order they will be consumed.
        Changing the returned list must not change the inventory."""
        return [tuple(lot) for lot in self._lots.get(sku, [])]
