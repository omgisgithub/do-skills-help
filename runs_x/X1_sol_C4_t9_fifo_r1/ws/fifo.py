"""FIFO inventory costing.

Money is handled as `decimal.Decimal`. Unit costs may be given as `Decimal`, `int` or `str`
(e.g. "2.335"); floats are rejected with `TypeError`.
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, localcontext
from typing import Hashable, Optional, Union


def _total_cost(amounts: list[tuple[int, Decimal]], *, cents: bool = False) -> Decimal:
    nonzero = [(qty, cost) for qty, cost in amounts if qty and cost]
    with localcontext() as context:
        if nonzero:
            lowest = min(cost.adjusted() - len(cost.as_tuple().digits) + 1 for _, cost in nonzero)
            highest = max(cost.adjusted() + len(str(qty)) for qty, cost in nonzero)
            # Allow exact products and sums even beyond the caller's Decimal precision.
            context.prec = max(28, highest - min(lowest, -2) + len(str(len(nonzero))) + 2)
        total = sum((qty * cost for qty, cost in nonzero), Decimal(0))
        return total.quantize(Decimal("0.01"), ROUND_HALF_UP) if cents else total


class Inventory:
    """Stock per SKU, kept as lots (purchases). Each lot is (date, qty, unit_cost)."""

    def __init__(self) -> None:
        self._lots: dict[Hashable, list[tuple[date, int, Decimal]]] = {}

    def buy(
        self, sku: Hashable, qty: int, unit_cost: Union[Decimal, int, str], when: date
    ) -> None:
        """Record a purchase of `qty` units (int > 0) at `unit_cost` each on date `when`.

        Purchases may be recorded out of order (a late invoice for an earlier date). Lots are
        always consumed oldest `when` first; lots with the same date in the order they were
        recorded. Raises ValueError for qty <= 0 or a negative unit cost.
        """
        if not isinstance(qty, int) or isinstance(qty, bool):
            raise TypeError("qty must be an integer")
        if qty <= 0:
            raise ValueError("qty must be positive")
        if isinstance(unit_cost, float):
            raise TypeError("use Decimal or str for money")
        cost = Decimal(unit_cost)
        if not cost.is_finite() or cost < 0:
            raise ValueError("cost must be finite and nonnegative")
        lots = self._lots.setdefault(sku, [])
        lots.append((when, qty, cost))
        lots.sort(key=lambda lot: lot[0])

    def sell(self, sku: Hashable, qty: int, when: date) -> Decimal:
        """Sell `qty` units (int > 0) and return the COGS as a Decimal with 2 decimals.

        COGS is the exact sum of qty x unit_cost over the units taken from each lot, rounded
        once at the end to cents, half up (2.345 -> 2.35). Only lots dated on or before
        `when` can be sold from. If there are not enough such units, raise ValueError and
        leave the inventory completely unchanged. Fully used lots disappear.
        """
        if not isinstance(qty, int) or isinstance(qty, bool):
            raise TypeError("qty must be an integer")
        if qty <= 0:
            raise ValueError("qty must be positive")
        lots = self._lots.get(sku, [])
        if sum(stock for purchased, stock, _ in lots if purchased <= when) < qty:
            raise ValueError("not enough stock")
        amounts = []
        updated = []
        remaining = qty
        for purchased, stock, cost in lots:
            take = min(remaining, stock) if purchased <= when else 0
            amounts.append((take, cost))
            if stock > take:
                updated.append((purchased, stock - take, cost))
            remaining -= take
        cogs = _total_cost(amounts, cents=True)
        self._lots[sku] = updated
        return cogs

    def on_hand(self, sku: Hashable) -> int:
        """Units of `sku` in stock (0 for an unknown SKU)."""
        return sum(l[1] for l in self._lots.get(sku, []))

    def value(self, sku: Optional[Hashable] = None) -> Decimal:
        """Exact remaining cost of stock (not rounded): one SKU, or all SKUs if sku is None."""
        skus = [sku] if sku is not None else list(self._lots)
        return _total_cost([(l[1], l[2]) for s in skus for l in self._lots.get(s, [])])

    def lots(self, sku: Hashable) -> list[tuple[date, int, Decimal]]:
        """A list of (when, qty, unit_cost) tuples for `sku`, in the order they will be consumed.
        Changing the returned list must not change the inventory."""
        return list(self._lots.get(sku, []))
