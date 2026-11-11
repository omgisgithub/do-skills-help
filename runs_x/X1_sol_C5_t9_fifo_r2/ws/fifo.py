"""FIFO inventory costing.

Money is handled as `decimal.Decimal`. Unit costs may be given as `Decimal`, `int` or `str`
(e.g. "2.335"); floats are rejected with `TypeError`.
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, localcontext


def _total_cost(entries):
    """Sum quantity/cost pairs without losing digits to the caller's context."""
    entries = list(entries)
    if not entries:
        return Decimal(0)
    lowest_place = min(cost.as_tuple().exponent for qty, cost in entries)
    highest_place = max(cost.adjusted() + len(str(qty)) for qty, cost in entries)
    with localcontext() as ctx:
        # Allow all fractional places, product digits, and carries from summing.
        ctx.prec = max(1, highest_place - lowest_place + len(str(len(entries))) + 1)
        return sum((qty * cost for qty, cost in entries), Decimal(0))


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
            raise TypeError("qty must be an integer")
        if qty <= 0:
            raise ValueError("qty must be positive")
        lots = self._lots.get(sku, [])
        if sum(lot[1] for lot in lots if lot[0] <= when) < qty:
            raise ValueError("not enough stock")
        consumed = []
        remaining_lots = []
        remaining = qty
        for lot_date, lot_qty, cost in lots:
            take = min(remaining, lot_qty) if lot_date <= when else 0
            if take:
                consumed.append((take, cost))
                remaining -= take
            if lot_qty > take:
                remaining_lots.append([lot_date, lot_qty - take, cost])
        cogs = _total_cost(consumed)
        with localcontext() as ctx:
            ctx.prec = max(len(cogs.as_tuple().digits), cogs.adjusted() + 3, 1)
            result = cogs.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self._lots[sku] = remaining_lots
        return result

    def on_hand(self, sku):
        """Units of `sku` in stock (0 for an unknown SKU)."""
        return sum(l[1] for l in self._lots.get(sku, []))

    def value(self, sku=None):
        """Exact remaining cost of stock (not rounded): one SKU, or all SKUs if sku is None."""
        skus = [sku] if sku is not None else list(self._lots)
        return _total_cost((lot[1], lot[2])
                           for s in skus for lot in self._lots.get(s, []))

    def lots(self, sku):
        """A list of (when, qty, unit_cost) tuples for `sku`, in the order they will be consumed.
        Changing the returned list must not change the inventory."""
        return [tuple(lot) for lot in self._lots.get(sku, [])]
