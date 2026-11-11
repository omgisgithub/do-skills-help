# legacy checkout pricing. DO NOT TOUCH (written 2019, nobody knows why it works)
from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, TypedDict

# Tier name -> discount fraction, applied after the bulk discount.
TIER_DISCOUNTS: dict[str, Decimal] = {
    "silver": Decimal("0.05"),
    "platinum": Decimal("0.20"),
    "gold": Decimal("0.12"),
}

# Category -> tax rate. Categories not listed use the "default" rate.
TAX_RATES: dict[str, Decimal] = {
    "books": Decimal("0.07"),
    "food": Decimal("0.07"),
    "default": Decimal("0.19"),
}


class PricedLine(TypedDict):
    """One priced cart line."""

    sku: str
    net: Decimal
    tax: Decimal


class Checkout(TypedDict):
    """Result of pricing a whole cart."""

    lines: list[PricedLine]
    total: Decimal


def _tier_factor(tier: object) -> Decimal:
    """Return the price multiplier for a tier; 1 when the tier has no discount."""
    # Compare with == instead of a dict lookup so unhashable values fall through
    # to "no discount" rather than raising TypeError.
    for name, discount in TIER_DISCOUNTS.items():
        if tier == name:
            return Decimal("1") - discount
    return Decimal("1")


def _tax_rate(category: object) -> Decimal:
    """Return the tax rate for a category, falling back to the default rate."""
    # Same == comparison as _tier_factor, for the same reason.
    for name, rate in TAX_RATES.items():
        if category == name:
            return rate
    return TAX_RATES["default"]


def price_line(item: Mapping[str, Any], customer: Mapping[str, Any]) -> PricedLine | None:
    """Price one cart item for a customer.

    Args:
        item: Cart item with ``sku``, ``price``, ``qty`` and an optional ``category``.
        customer: Customer with an optional ``tier``.

    Returns:
        The ``sku``, ``net`` and ``tax`` for the item, each rounded to cents, or
        ``None`` when the quantity is zero or negative.
    """
    p = Decimal(str(item["price"]))
    q = item["qty"]
    if q <= 0:
        return None
    line = p * q
    if q >= 10:
        line = line * Decimal("0.9")
    line = line * _tier_factor(customer.get("tier"))
    line = line.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    rate = _tax_rate(item.get("category"))
    tax = (line * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"sku": item["sku"], "net": line, "tax": tax}


def checkout(
    cart: Iterable[Mapping[str, Any]],
    customer: Mapping[str, Any],
    coupon: str | None = None,
) -> Checkout:
    """Price a cart and apply an optional coupon.

    Args:
        cart: Items to price. Items with ``qty <= 0`` are skipped.
        customer: Customer with an optional ``tier``.
        coupon: Coupon code, or ``None``. Raises ``ValueError`` if unknown.

    Returns:
        The priced lines and the total, quantized to cents.

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
