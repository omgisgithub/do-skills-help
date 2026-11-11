"""Legacy checkout pricing.

The discount ordering, per-line rounding, and coupon handling here reproduce
the original implementation exactly; existing callers depend on the results.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Mapping, Optional, Sequence

#: Tier name -> discount as a fraction of the price.
TIER_DISCOUNTS: Dict[str, Decimal] = {
    "silver": Decimal("0.05"),
    "platinum": Decimal("0.20"),
    "gold": Decimal("0.12"),
}

#: Item category -> tax rate. Any missing or unknown category uses "default".
TAX_RATES: Dict[str, Decimal] = {
    "books": Decimal("0.07"),
    "food": Decimal("0.07"),
    "default": Decimal("0.19"),
}

BULK_QTY_THRESHOLD = 10
BULK_DISCOUNT = Decimal("0.9")

_CENT = Decimal("0.01")
_ONE = Decimal("1")


def price_line(
    item: Mapping[str, Any], customer: Mapping[str, Any]
) -> Optional[Dict[str, Any]]:
    """Price one cart item.

    The bulk discount is applied before the tier discount, and the resulting net
    amount is rounded before tax is calculated, matching the original behavior.

    Args:
        item: Cart item with ``sku``, ``price``, ``qty``, and optional ``category``.
        customer: Customer with an optional ``tier``.

    Returns:
        A dict with ``sku``, ``net``, and ``tax``, or ``None`` when ``qty`` is not
        positive.
    """
    price = Decimal(str(item["price"]))
    quantity = item["qty"]
    if quantity <= 0:
        return None

    net = price * quantity
    if quantity >= BULK_QTY_THRESHOLD:
        net = net * BULK_DISCOUNT

    tier_discount = TIER_DISCOUNTS.get(customer.get("tier"))
    if tier_discount is not None:
        net = net * (_ONE - tier_discount)

    tax_rate = TAX_RATES.get(item.get("category"), TAX_RATES["default"])

    net = net.quantize(_CENT, rounding=ROUND_HALF_UP)
    tax = (net * tax_rate).quantize(_CENT, rounding=ROUND_HALF_UP)
    return {"sku": item["sku"], "net": net, "tax": tax}


def checkout(
    cart: Sequence[Mapping[str, Any]],
    customer: Mapping[str, Any],
    coupon: Optional[str] = None,
) -> Dict[str, Any]:
    """Price a cart, apply an optional coupon, and return the lines and total.

    Args:
        cart: Sequence of cart items; items with non-positive quantity are ignored.
        customer: Customer whose ``tier`` selects a discount, if any.
        coupon: Optional coupon code. ``WELCOME5``, ``HALFSHIP``, and ``PCT<n>``
            are understood; anything else raises ``ValueError``.

    Returns:
        A dict with the priced ``lines`` and the final ``total``, both quantized to
        cents.

    Raises:
        ValueError: If the coupon code is not recognized.
    """
    total = Decimal("0")
    lines: List[Dict[str, Any]] = []

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
            percent = int(coupon[3:])
            if percent > 30:
                percent = 30
            total = total - (total * percent / 100).quantize(
                _CENT, rounding=ROUND_HALF_UP
            )
        else:
            raise ValueError("unknown coupon")

    if total < 0:
        total = Decimal("0")

    return {"lines": lines, "total": total.quantize(_CENT)}
