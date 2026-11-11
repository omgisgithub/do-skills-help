"""FIFO inventory costing.

Money is handled as `decimal.Decimal`. Unit costs may be given as `Decimal`, `int` or `str`
(e.g. "2.335"); floats are rejected with `TypeError`.
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, localcontext


def _cost_total(items, rounded=False):
    """Sum (quantity, cost) pairs without losing digits to decimal precision."""
    items = list(items)
    # Multiplication needs at most the sum of the operand digit counts;
    # alignment and addition may require further digits and a carry.
    lowest = min((cost.as_tuple().exponent for _, cost in items), default=0)
    highest = max((cost.as_tuple().exponent + len(cost.as_tuple().digits)
                   + len(str(qty)) for qty, cost in items), default=0)
    with localcontext() as context:
        context.prec = max(28, highest - min(lowest, -2)
                           + len(str(len(items))) + 1)
        total = sum((qty * cost for qty, cost in items), Decimal(0))
        return total.quantize(Decimal("0.01"), ROUND_HALF_UP) if rounded else total


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
            raise TypeError("qty must be an int")
        if qty <= 0:
            raise ValueError("qty must be positive")
        if not isinstance(unit_cost, (Decimal, int, str)):
            raise TypeError("use Decimal or str for money")
        cost = Decimal(unit_cost)
        if not cost.is_finite() or cost < 0:
            raise ValueError("negative cost")
        lots = self._lots.setdefault(sku, [])
        lots.append([when, qty, cost])
        lots.sort(key=lambda lot: lot[0])

    def sell(self, sku, qty, when):
        """Sell `qty` units (int > 0) and return the COGS as a Decimal with 2 decimals.

        COGS is the exact sum of qty x unit_cost over the units taken from each lot, rounded
        once at the end to cents, half up (2.345 -> 2.35). Only lots dated on or before
        `when` can be sold from. If there are not enough such units, raise ValueError and
        leave the inventory completely unchanged. Fully used lots disappear.
        """
        if not isinstance(qty, int):
            raise TypeError("qty must be an int")
        if qty <= 0:
            raise ValueError("qty must be positive")
        lots = self._lots.get(sku, [])
        if sum(lot[1] for lot in lots if lot[0] <= when) < qty:
            raise ValueError("not enough stock")
        consumed = []
        updated = []
        remaining = qty
        for lot_date, lot_qty, cost in lots:
            take = min(remaining, lot_qty) if lot_date <= when else 0
            if take:
                consumed.append((take, cost))
            if lot_qty > take:
                updated.append([lot_date, lot_qty - take, cost])
            remaining -= take
        cogs = _cost_total(consumed, rounded=True)
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
