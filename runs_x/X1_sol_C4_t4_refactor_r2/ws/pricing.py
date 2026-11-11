"""Calculate checkout prices with bulk and customer-tier discounts."""

from collections.abc import Iterable, Mapping
from decimal import Decimal, ROUND_HALF_UP, localcontext
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
    """Describe a rounded cart line."""

    sku: object
    net: Decimal
    tax: Decimal


class CheckoutResult(TypedDict):
    """Describe priced lines and the final checkout total."""

    lines: list[PricedLine]
    total: Decimal


# Legacy callers accept heterogeneous values; annotations must not restrict runtime inputs.
def price_line(item: Mapping[str, Any], customer: Mapping[str, Any]) -> Optional[PricedLine]:
    """Price an item, applying bulk and tier discounts before rounding net and tax.

    Return None for nonpositive quantities, after the legacy price conversion.
    Gold customers receive a 12 percent tier discount.
    """
    p = Decimal(str(item["price"]))
    q = item["qty"]
    if q <= 0:
        return None
    line = p * q
    if q >= 10:
        line = line * Decimal("0.9")
    # Equality lookups preserve support for unhashable, unknown tier/category values.
    for tier, discount in TIER_DISCOUNTS.items():
        if customer.get("tier") == tier:
            # Construct the factor exactly even when callers lower Decimal precision.
            with localcontext() as context:
                context.prec = max(context.prec, 3)
                factor = Decimal("1.00") - discount
            line = line * factor
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
    cart: Iterable[Mapping[str, Any]],
    customer: Mapping[str, Any],
    coupon: Optional[str] = None,
) -> CheckoutResult:
    """Price cart lines, then apply a coupon to their tax-inclusive total."""
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
