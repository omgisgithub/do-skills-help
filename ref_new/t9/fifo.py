"""Reference fix for t9_fifo (hidden)."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


class Inventory:
    def __init__(self):
        self._lots = {}
        self._seq = 0

    def buy(self, sku, qty, unit_cost, when):
        if qty <= 0:
            raise ValueError("qty must be positive")
        if isinstance(unit_cost, float):
            raise TypeError("use Decimal or str for money")
        cost = Decimal(unit_cost)
        if cost < 0:
            raise ValueError("negative cost")
        self._seq += 1
        lots = self._lots.setdefault(sku, [])
        lots.append([when, self._seq, qty, cost])
        lots.sort(key=lambda l: (l[0], l[1]))

    def sell(self, sku, qty, when):
        if qty <= 0:
            raise ValueError("qty must be positive")
        lots = self._lots.get(sku, [])
        avail = sum(l[2] for l in lots if l[0] <= when)
        if avail < qty:
            raise ValueError("not enough stock")
        cogs = Decimal("0")
        remaining = qty
        for lot in lots:
            if remaining == 0:
                break
            if lot[0] > when:
                continue
            take = min(remaining, lot[2])
            cogs += take * lot[3]
            lot[2] -= take
            remaining -= take
        self._lots[sku] = [l for l in lots if l[2] > 0]
        return cogs.quantize(Decimal("0.01"), ROUND_HALF_UP)

    def on_hand(self, sku):
        return sum(l[2] for l in self._lots.get(sku, []))

    def value(self, sku=None):
        skus = [sku] if sku is not None else list(self._lots)
        return sum((l[2] * l[3] for s in skus for l in self._lots.get(s, [])), Decimal("0"))

    def lots(self, sku):
        return [(l[0], l[2], l[3]) for l in self._lots.get(sku, [])]
