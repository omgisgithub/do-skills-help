"""FIFO inventory costing.

Money is handled as `decimal.Decimal`. Unit costs may be given as `Decimal`, `int` or `str`
(e.g. "2.335"); floats are rejected with `TypeError`.
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, localcontext
from typing import Optional, Union


_Lot = tuple[date, int, Decimal]


def _total_cost(lots: list[_Lot]) -> Decimal:
    if not lots:
        return Decimal(0)
    # Cover every decimal place and carry so the caller's context cannot round stock value.
    lowest_place = min(cost.adjusted() - len(cost.as_tuple().digits) + 1
                       for _, _, cost in lots)
    highest_place = max(cost.adjusted() + len(str(qty)) for _, qty, cost in lots)
    with localcontext() as context:
        context.prec = max(1, highest_place - lowest_place + len(str(len(lots))) + 1)
        return sum((qty * cost for _, qty, cost in lots), Decimal(0))


class Inventory:
    """Stock per SKU, kept as lots (purchases). Each lot is (date, qty, unit_cost)."""

    def __init__(self) -> None:
        self._lots: dict[str, list[_Lot]] = {}

    def buy(self, sku: str, qty: int, unit_cost: Union[Decimal, int, str], when: date) -> None:
        """Record a purchase of `qty` units (int > 0) at `unit_cost` each on date `when`.

        Purchases may be recorded out of order (a late invoice for an earlier date). Lots are
        always consumed oldest `when` first; lots with the same date in the order they were
        recorded. Raises ValueError for qty <= 0 or a negative unit cost.
        """
        if qty <= 0:
            raise ValueError("qty must be positive")
        if isinstance(unit_cost, float):
            raise TypeError("use Decimal or str for money")
        cost = Decimal(unit_cost)
        if not cost.is_finite() or cost < 0:
            raise ValueError("unit cost must be finite and nonnegative")
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
        if qty <= 0:
            raise ValueError("qty must be positive")
        lots = self._lots.get(sku, [])
        if sum(qty_in_lot for lot_date, qty_in_lot, _ in lots if lot_date <= when) < qty:
            raise ValueError("not enough stock")
        sold = []
        updated = []
        remaining = qty
        for lot_date, qty_in_lot, cost in lots:
            take = min(remaining, qty_in_lot) if lot_date <= when else 0
            if take:
                sold.append((lot_date, take, cost))
            if qty_in_lot > take:
                updated.append((lot_date, qty_in_lot - take, cost))
            remaining -= take
        cogs = _total_cost(sold)
        with localcontext() as context:
            context.prec = max(1, cogs.adjusted() + 4)
            result = cogs.quantize(Decimal("0.01"), ROUND_HALF_UP)
        self._lots[sku] = updated
        return result

    def on_hand(self, sku: str) -> int:
        """Units of `sku` in stock (0 for an unknown SKU)."""
        return sum(l[1] for l in self._lots.get(sku, []))

    def value(self, sku: Optional[str] = None) -> Decimal:
        """Exact remaining cost of stock (not rounded): one SKU, or all SKUs if sku is None."""
        skus = [sku] if sku is not None else list(self._lots)
        return _total_cost([lot for s in skus for lot in self._lots.get(s, [])])

    def lots(self, sku: str) -> list[_Lot]:
        """A list of (when, qty, unit_cost) tuples for `sku`, in the order they will be consumed.
        Changing the returned list must not change the inventory."""
        return list(self._lots.get(sku, []))
