# legacy checkout pricing. DO NOT TOUCH (written 2019, nobody knows why it works)
from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

# Discount fractions per customer tier. Unknown or missing tiers get no tier discount.
TIER_DISCOUNTS: Mapping[str, Decimal] = {
    "silver": Decimal("0.05"),
    "gold": Decimal("0.12"),
    "platinum": Decimal("0.20"),
}

# Tax rate per item category. Any other category falls back to the "default" rate.
TAX_RATES: Mapping[str, Decimal] = {
    "books": Decimal("0.07"),
    "food": Decimal("0.07"),
    "default": Decimal("0.19"),
}


def price_line(item: Mapping[str, Any], customer: Mapping[str, Any]) -> dict[str, Any] | None:
    """Price a single cart item after bulk and tier discounts, plus tax.

    Bulk discounts apply to quantities of 10 or more. Rounding happens on the
    net amount before tax is computed, so the order of operations matters.

    Args:
        item: Cart item with ``sku``, ``price``, ``qty`` and optional ``category``.
        customer: Customer data. The optional ``tier`` key selects a tier discount.

    Returns:
        A dict with ``sku``, ``net`` and ``tax`` as Decimals, or ``None`` if the
        item's quantity is zero or negative.
    """
    # Loosely typed cart dicts come from callers; values are converted here.
    p = Decimal(str(item["price"]))
    q = item["qty"]
    if q <= 0:
        return None
    line = p * q
    if q >= 10:
        line = line * Decimal("0.9")
    tier_discount = TIER_DISCOUNTS.get(customer.get("tier"), Decimal("0"))
    line = line * (Decimal("1") - tier_discount)
    tax_rate = TAX_RATES.get(item.get("category"), TAX_RATES["default"])
    line = line.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    tax = (line * tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"sku": item["sku"], "net": line, "tax": tax}


def checkout(
    cart: Iterable[Mapping[str, Any]],
    customer: Mapping[str, Any],
    coupon: str | None = None,
) -> dict[str, Any]:
    """Total a cart for a customer, applying an optional coupon.

    Args:
        cart: Cart items, each accepted by ``price_line``.
        customer: Customer data passed through to ``price_line``.
        coupon: Coupon code: ``WELCOME5``, ``HALFSHIP``, or ``PCT<n>`` (capped at 30%).

    Returns:
        A dict with ``lines`` (the priced items, skipping zero quantities) and
        ``total`` quantized to cents.

    Raises:
        ValueError: If the coupon code is not recognised.
    """
    total = Decimal("0")
    lines: list[dict[str, Any]] = []
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
