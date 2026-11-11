"""Checkout pricing: per-line discounts, tax, and coupon handling."""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, Iterable, Mapping, Optional

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


def price_line(
    item: Mapping[str, Any], customer: Mapping[str, Any]
) -> Optional[Dict[str, Any]]:
    """Price one cart item.

    Args:
        item: Cart item with ``sku``, ``price``, ``qty``, and optional ``category``.
        customer: Customer record; an unknown or missing ``tier`` gets no discount.

    Returns:
        A ``{"sku", "net", "tax"}`` dict, or ``None`` when ``qty`` is not positive.
    """
    price = Decimal(str(item["price"]))
    qty = item["qty"]
    if qty <= 0:
        return None

    line = price * qty
    if qty >= 10:
        line = line * Decimal("0.9")

    discount = TIER_DISCOUNTS.get(customer.get("tier"), Decimal("0"))
    if discount:
        line = line * (Decimal("1") - discount)

    line = line.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    tax_rate = TAX_RATES.get(item.get("category"), TAX_RATES["default"])
    tax = (line * tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"sku": item["sku"], "net": line, "tax": tax}


def checkout(
    cart: Iterable[Mapping[str, Any]],
    customer: Mapping[str, Any],
    coupon: Optional[str] = None,
) -> Dict[str, Any]:
    """Price a whole cart and apply any coupon.

    Args:
        cart: Cart items, each accepted by :func:`price_line`.
        customer: Customer record used for tier discounts.
        coupon: Optional coupon code.

    Returns:
        A ``{"lines", "total"}`` dict.

    Raises:
        ValueError: If the coupon code is unknown.
    """
    total = Decimal("0")
    lines = []
    for item in cart:
        line = price_line(item, customer)
        if line is None:
            continue
        lines.append(line)
        total = total + line["net"] + line["tax"]

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
            total = total - (total * pct / 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        else:
            raise ValueError("unknown coupon")

    if total < 0:
        total = Decimal("0")
    return {"lines": lines, "total": total.quantize(Decimal("0.01"))}
