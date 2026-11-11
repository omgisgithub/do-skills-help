"""FIFO inventory costing.

Money is handled as `decimal.Decimal`. Unit costs may be given as `Decimal`, `int` or `str`
(e.g. "2.335"); floats are rejected with `TypeError`.
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Union


class Inventory:
    """Stock per SKU, kept as lots (purchases). Each lot is (date, qty, unit_cost)."""

    def __init__(self) -> None:
        self._lots: dict[str, list[tuple[date, int, Decimal]]] = {}

    def buy(self, sku: str, qty: int, unit_cost: Union[Decimal, int, str], when: date) -> None:
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
        lots.append((when, qty, cost))
        lots.sort(key=lambda lot: lot[0])

    def sell(self, sku: str, qty: int, when: date) -> Decimal:
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
        cogs = Decimal("0")
        remaining = qty
        updated_lots = []
        for lot_date, lot_qty, cost in lots:
            if remaining == 0 or lot_date > when:
                updated_lots.append((lot_date, lot_qty, cost))
                continue
            take = min(remaining, lot_qty)
            cogs += take * cost
            if take < lot_qty:
                updated_lots.append((lot_date, lot_qty - take, cost))
            remaining -= take
        if remaining:
            raise ValueError("not enough stock")
        result = cogs.quantize(Decimal("0.01"), ROUND_HALF_UP)
        self._lots[sku] = updated_lots
        return result

    def on_hand(self, sku: str) -> int:
        """Units of `sku` in stock (0 for an unknown SKU)."""
        return sum(l[1] for l in self._lots.get(sku, []))

    def value(self, sku: Optional[str] = None) -> Decimal:
        """Exact remaining cost of stock (not rounded): one SKU, or all SKUs if sku is None."""
        skus = [sku] if sku is not None else list(self._lots)
        return sum((l[1] * l[2] for s in skus for l in self._lots.get(s, [])), Decimal("0"))

    def lots(self, sku: str) -> list[tuple[date, int, Decimal]]:
        """A list of (when, qty, unit_cost) tuples for `sku`, in the order they will be consumed.
        Changing the returned list must not change the inventory."""
        return list(self._lots.get(sku, []))
