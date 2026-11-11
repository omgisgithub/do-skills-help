"""Calculate checkout prices with legacy discount and rounding rules."""

from collections.abc import Iterable, Mapping
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional, TypedDict


TIER_DISCOUNTS = {
    "silver": Decimal("0.05"),
    "platinum": Decimal("0.20"),
    "gold": Decimal("0.12"),
}
TAX_RATES = {
    "books": Decimal("0.07"),
    "food": Decimal("0.07"),
    "default": Decimal("0.19"),
}


class PricedLine(TypedDict):
    """Describe a cart line after discounts and tax."""

    sku: object
    net: Decimal
    tax: Decimal


class CheckoutResult(TypedDict):
    """Describe priced lines and the total after coupons."""

    lines: list[PricedLine]
    total: Decimal


# Legacy items accept arbitrary price and quantity objects supporting decimal arithmetic.
def price_line(item: Mapping[str, Any], customer: Mapping[str, object]) -> Optional[PricedLine]:
    """Price one item, or skip it when its quantity is nonpositive."""
    p = Decimal(str(item["price"]))
    q = item["qty"]
    if q <= 0:
        return None
    line = p * q
    if q >= 10:
        line = line * Decimal("0.9")
    # Equality comparisons preserve support for unhashable, unknown tier values.
    for tier, discount in TIER_DISCOUNTS.items():
        if customer.get("tier") == tier:
            line = line * (Decimal("1.00") - discount)
            break
    tax = TAX_RATES["default"]
    for category, rate in TAX_RATES.items():
        if item.get("category") == category:
            tax = rate
            break
    line = line.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    t = (line * tax).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"sku": item["sku"], "net": line, "tax": t}


def checkout(
    cart: Iterable[Mapping[str, Any]],  # Preserve the legacy item value types.
    customer: Mapping[str, object],
    coupon: Optional[str] = None,
) -> CheckoutResult:
    """Price cart items and apply a coupon to the tax-inclusive total."""
    total = Decimal("0")
    lines = []
    for item in cart:
        priced = price_line(item, customer)
        if priced is None:
            continue
        lines.append(priced)
        total = total + priced["net"] + priced["tax"]
    if coupon is not None:
        if coupon == "WELCOME5":
            if total >= Decimal("20"):
                total = total - Decimal("5")
        elif coupon == "HALFSHIP":
            pass
        elif coupon.startswith("PCT"):
            pct = int(coupon[3:])
            if pct > 30:
                pct = 30
            total = total - (total * pct / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            raise ValueError("unknown coupon")
    if total < 0:
        total = Decimal("0")
    return {"lines": lines, "total": total.quantize(Decimal("0.01"))}
