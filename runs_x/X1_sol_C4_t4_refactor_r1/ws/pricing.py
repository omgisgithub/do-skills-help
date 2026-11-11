"""Calculate checkout prices with per-line discounts and taxes."""

from collections.abc import Iterable, Mapping
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any, Optional, TypedDict


# Legacy inputs permit arbitrary price representations, quantities, and SKU values.
class PricedLine(TypedDict):
    """Describe a rounded cart line."""

    sku: Any
    net: Decimal
    tax: Decimal


class CheckoutResult(TypedDict):
    """Describe the priced lines and final checkout total."""

    lines: list[PricedLine]
    total: Decimal


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


def price_line(item: Mapping[str, Any], customer: Mapping[str, Any]) -> Optional[PricedLine]:
    """Price one item, returning no line for a nonpositive quantity.

    Apply bulk and tier discounts before rounding net, then tax the rounded net.
    Price conversion intentionally precedes the quantity check for compatibility.
    """
    p = Decimal(str(item["price"]))
    q = item["qty"]
    if q <= 0:
        return None
    line = p * q
    if q >= 10:
        line = line * Decimal("0.9")
    # Equality checks preserve the legacy fallback for unhashable tier/category values.
    for tier, discount in TIER_DISCOUNTS.items():
        if customer.get("tier") == tier:
            # Derive the exact multiplier without rounding in the caller's context.
            with localcontext() as context:
                context.prec = max(context.prec, 28)
                multiplier = Decimal("1") - discount
            line = line * multiplier
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
    """Price cart lines and apply a coupon to their combined net and tax."""
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
