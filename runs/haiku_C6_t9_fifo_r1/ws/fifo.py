"""FIFO inventory costing.

Money is handled as `decimal.Decimal`. Unit costs may be given as `Decimal`, `int` or `str`
(e.g. "2.335"); floats are rejected with `TypeError`.
"""
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def _unit_cost(unit_cost):
    if isinstance(unit_cost, bool) or not isinstance(unit_cost, (Decimal, int, str)):
        raise TypeError("use Decimal or str for money")
    try:
        cost = Decimal(unit_cost)
    except InvalidOperation:
        raise ValueError("invalid cost")
    if not cost.is_finite():
        raise ValueError("invalid cost")
    return cost


class Inventory:
    """Stock per SKU, kept as lots (purchases). Each lot is (date, qty, unit_cost)."""

    def __init__(self):
        self._lots = {}  # sku -> list of [when, qty, unit_cost], in consumption order

    def buy(self, sku, qty, unit_cost, when):
        """Record a purchase of `qty` units (int > 0) at `unit_cost` each on date `when`.

        Purchases may be recorded out of order (a late invoice for an earlier date). Lots are
        always consumed oldest `when` first; lots with the same date in the order they were
        recorded. Raises ValueError for qty <= 0 or a negative unit cost.
        """
        if isinstance(qty, bool) or not isinstance(qty, int):
            raise TypeError("qty must be an int")
        if qty <= 0:
            raise ValueError("qty must be positive")
        cost = _unit_cost(unit_cost)
        if cost < 0:
            raise ValueError("negative cost")
        lots = self._lots.setdefault(sku, [])
        lots.append([when, qty, cost])
        # sort is stable, so same-date lots keep the order they were recorded in
        lots.sort(key=lambda lot: lot[0])

    def sell(self, sku, qty, when):
        """Sell `qty` units (int > 0) and return the COGS as a Decimal with 2 decimals.

        COGS is the exact sum of qty x unit_cost over the units taken from each lot, rounded
        once at the end to cents, half up (2.345 -> 2.35). Only lots dated on or before
        `when` can be sold from. If there are not enough such units, raise ValueError and
        leave the inventory completely unchanged. Fully used lots disappear.
        """
        if isinstance(qty, bool) or not isinstance(qty, int):
            raise TypeError("qty must be an int")
        if qty <= 0:
            raise ValueError("qty must be positive")
        lots = self._lots.get(sku, [])
        eligible = [lot for lot in lots if lot[0] <= when]
        if sum(lot[1] for lot in eligible) < qty:
            raise ValueError("not enough stock")
        cogs = Decimal(0)
        remaining = qty
        for lot in eligible:
            if remaining == 0:
                break
            take = min(remaining, lot[1])
            cogs += take * lot[2]
            lot[1] -= take
            remaining -= take
        self._lots[sku] = [lot for lot in lots if lot[1] > 0]
        return cogs.quantize(Decimal("0.01"), ROUND_HALF_UP)

    def on_hand(self, sku):
        """Units of `sku` in stock (0 for an unknown SKU)."""
        return sum(lot[1] for lot in self._lots.get(sku, []))

    def value(self, sku=None):
        """Exact remaining cost of stock (not rounded): one SKU, or all SKUs if sku is None."""
        skus = [sku] if sku is not None else list(self._lots)
        total = Decimal(0)
        for s in skus:
            for lot in self._lots.get(s, []):
                total += lot[1] * lot[2]
        return total

    def lots(self, sku):
        """A list of (when, qty, unit_cost) tuples for `sku`, in the order they will be consumed.
        Changing the returned list must not change the inventory."""
        return [(when, qty, cost) for when, qty, cost in self._lots.get(sku, [])]
