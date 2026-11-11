"""FIFO inventory costing.

Money is handled as `decimal.Decimal`. Unit costs may be given as `Decimal`, `int` or `str`
(e.g. "2.335"); floats are rejected with `TypeError`.
"""
from decimal import Context, Decimal, MAX_EMAX, MIN_EMIN, ROUND_HALF_UP, localcontext


def _total_cost(lots, rounded=False):
    """Sum lot costs with enough precision for exact multiplication and addition."""
    if not lots:
        return Decimal("0.00") if rounded else Decimal(0)
    # The total cannot have more integer digits than the largest unit cost
    # times the total quantity. Preserve the smallest fractional place too.
    exponent = min(-2, min(lot[2].as_tuple().exponent for lot in lots))
    integer_digits = max(lot[2].adjusted() for lot in lots)
    quantity_digits = len(str(sum(lot[1] for lot in lots)))
    precision = max(1, integer_digits + quantity_digits - exponent + 2)
    # Isolate accounting arithmetic from the caller's precision, limits and traps.
    with localcontext(Context(prec=precision, Emin=MIN_EMIN, Emax=MAX_EMAX)):
        total = sum((qty * cost for _, qty, cost in lots), Decimal(0))
        if rounded:
            return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
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
        if not isinstance(unit_cost, (Decimal, int, str)):
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
        consumed = []
        remaining = qty
        for lot in lots:
            if remaining == 0:
                break
            if lot[0] > when:
                continue
            take = min(remaining, lot[1])
            consumed.append((lot[0], take, lot[2]))
            remaining -= take
        cogs = _total_cost(consumed, rounded=True)
        remaining = qty
        for lot in lots:
            if remaining == 0:
                break
            if lot[0] > when:
                continue
            take = min(remaining, lot[1])
            lot[1] -= take
            remaining -= take
        self._lots[sku] = [lot for lot in lots if lot[1] > 0]
        return cogs

    def on_hand(self, sku):
        """Units of `sku` in stock (0 for an unknown SKU)."""
        return sum(l[1] for l in self._lots.get(sku, []))

    def value(self, sku=None):
        """Exact remaining cost of stock (not rounded): one SKU, or all SKUs if sku is None."""
        skus = [sku] if sku is not None else list(self._lots)
        return _total_cost([lot for s in skus for lot in self._lots.get(s, [])])

    def lots(self, sku):
        """A list of (when, qty, unit_cost) tuples for `sku`, in the order they will be consumed.
        Changing the returned list must not change the inventory."""
        return [tuple(lot) for lot in self._lots.get(sku, [])]
