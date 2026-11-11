"""FIFO inventory costing.

Money is handled as `decimal.Decimal`. Unit costs may be given as `Decimal`, `int` or `str`
(e.g. "2.335"); floats are rejected with `TypeError`.
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, Context

_CTX = Context(prec=500)


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
        self._check_qty(qty)
        if isinstance(unit_cost, float) or not isinstance(unit_cost, (Decimal, int, str)):
            raise TypeError("use Decimal, int or str for money")
        if isinstance(unit_cost, bool):
            raise TypeError("use Decimal, int or str for money")
        cost = Decimal(unit_cost)
        if not cost.is_finite():
            raise ValueError("cost must be finite")
        if cost < 0:
            raise ValueError("negative cost")
        lots = self._lots.setdefault(sku, [])
        i = len(lots)
        while i > 0 and lots[i - 1][0] > when:
            i -= 1
        lots.insert(i, [when, qty, cost])

    @staticmethod
    def _check_qty(qty):
        if isinstance(qty, bool) or not isinstance(qty, int):
            raise TypeError("qty must be an int")
        if qty <= 0:
            raise ValueError("qty must be positive")

    def sell(self, sku, qty, when):
        """Sell `qty` units (int > 0) and return the COGS as a Decimal with 2 decimals.

        COGS is the exact sum of qty x unit_cost over the units taken from each lot, rounded
        once at the end to cents, half up (2.345 -> 2.35). Only lots dated on or before
        `when` can be sold from. If there are not enough such units, raise ValueError and
        leave the inventory completely unchanged. Fully used lots disappear.
        """
        self._check_qty(qty)
        lots = self._lots.get(sku, [])
        total = Decimal(0)
        remaining = qty
        takes = []
        for lot in lots:
            if remaining == 0:
                break
            if lot[0] > when:
                continue
            take = min(remaining, lot[1])
            total = _CTX.add(total, _CTX.multiply(take, lot[2]))
            takes.append((lot, take))
            remaining -= take
        if remaining:
            raise ValueError("not enough stock")
        for lot, take in takes:
            lot[1] -= take
        self._lots[sku] = [l for l in lots if l[1] > 0]
        return total.quantize(Decimal("0.01"), ROUND_HALF_UP, context=_CTX)

    def on_hand(self, sku):
        """Units of `sku` in stock (0 for an unknown SKU)."""
        return sum(l[1] for l in self._lots.get(sku, []))

    def value(self, sku=None):
        """Exact remaining cost of stock (not rounded): one SKU, or all SKUs if sku is None."""
        skus = [sku] if sku is not None else list(self._lots)
        total = Decimal(0)
        for s in skus:
            for l in self._lots.get(s, []):
                total = _CTX.add(total, _CTX.multiply(l[1], l[2]))
        return total

    def lots(self, sku):
        """A list of (when, qty, unit_cost) tuples for `sku`, in the order they will be consumed.
        Changing the returned list must not change the inventory."""
        return [tuple(l) for l in self._lots.get(sku, [])]
