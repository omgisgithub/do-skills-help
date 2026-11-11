# legacy checkout pricing. DO NOT TOUCH (written 2019, nobody knows why it works)
from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, TypedDict

TIER_DISCOUNTS: dict[str, Decimal] = {
    "silver": Decimal("0.05"),
    "gold": Decimal("0.12"),
    "platinum": Decimal("0.20"),
}

TAX_RATES: dict[str, Decimal] = {
    "books": Decimal("0.07"),
    "food": Decimal("0.07"),
    "default": Decimal("0.19"),
}

BULK_MIN_QTY = 10
BULK_FACTOR = Decimal("0.9")


class PricedLine(TypedDict):
    """One priced cart line."""

    sku: str
    net: Decimal
    tax: Decimal


def price_line(item: Mapping[str, Any], customer: Mapping[str, Any]) -> PricedLine | None:
    """Price one cart item for a customer.

    Applies the bulk discount, then the tier discount, then rounds the net
    amount before computing tax on it.

    Args:
        item: Cart item with ``sku``, ``price`` and ``qty``, and an optional ``category``.
        customer: Customer data; its ``tier`` selects the discount, if any.

    Returns:
        The priced line, or None if the item's quantity is zero or negative.
    """
    # Price and qty are read before the qty check so bad input fails the same way as before.
    price = Decimal(str(item["price"]))
    qty = item["qty"]
    if qty <= 0:
        return None
    line = price * qty
    if qty >= BULK_MIN_QTY:
        line = line * BULK_FACTOR
    # Unknown or missing tiers get no discount.
    tier_discount = TIER_DISCOUNTS.get(customer.get("tier"), Decimal("0"))
    line = line * (Decimal("1") - tier_discount)
    line = line.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    tax_rate = TAX_RATES.get(item.get("category"), TAX_RATES["default"])
    tax = (line * tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"sku": item["sku"], "net": line, "tax": tax}


def checkout(
    cart: Sequence[Mapping[str, Any]],
    customer: Mapping[str, Any],
    coupon: str | None = None,
) -> dict[str, Any]:
    """Price a cart and apply an optional coupon.

    Args:
        cart: Items to price, as accepted by ``price_line``.
        customer: Customer data, as accepted by ``price_line``.
        coupon: Coupon code: ``WELCOME5``, ``HALFSHIP``, or ``PCT<n>`` (capped at 30).

    Returns:
        A dict with ``lines`` (the priced lines) and ``total`` (quantized to cents).

    Raises:
        ValueError: If the coupon code is not recognised.
    """
    total = Decimal("0")
    lines: list[PricedLine] = []
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
