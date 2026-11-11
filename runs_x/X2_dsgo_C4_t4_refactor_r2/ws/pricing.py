# legacy checkout pricing. Originally written 2019; refactored to share one
# pricing path across tiers without changing any observable result.
from decimal import Decimal, ROUND_HALF_UP

# Discount fraction per customer tier. A tier that is absent (or unknown) pays
# the full price, which is the historical behaviour for every non-listed tier.
TIER_DISCOUNTS = {
    "silver": Decimal("0.05"),
    "platinum": Decimal("0.20"),
    "gold": Decimal("0.12"),
}

# Tax rate per item category; "default" covers any other or missing category.
TAX_RATES = {
    "books": Decimal("0.07"),
    "food": Decimal("0.07"),
    "default": Decimal("0.19"),
}

_CENT = Decimal("0.01")
_ONE = Decimal("1")
_BULK_QTY = 10
_BULK_DISCOUNT = Decimal("0.10")


def price_line(item, customer):
    """Price a single cart line.

    Args:
        item: Cart item with ``sku``, ``price``, ``qty`` and optional ``category``.
        customer: Customer mapping whose ``tier`` selects the tier discount.

    Returns:
        A ``{"sku", "net", "tax"}`` dict, or ``None`` when ``qty <= 0``.
    """
    # Convert the price before the quantity check so invalid prices behave
    # exactly as they did in the original implementation.
    price = Decimal(str(item["price"]))
    qty = item["qty"]
    if qty <= 0:
        return None

    line = price * qty
    if qty >= _BULK_QTY:
        line = line * (_ONE - _BULK_DISCOUNT)
    discount = TIER_DISCOUNTS.get(customer.get("tier"))
    if discount is not None:
        line = line * (_ONE - discount)

    tax = TAX_RATES.get(item.get("category"), TAX_RATES["default"])
    net = line.quantize(_CENT, rounding=ROUND_HALF_UP)
    tax_amount = (net * tax).quantize(_CENT, rounding=ROUND_HALF_UP)
    return {"sku": item["sku"], "net": net, "tax": tax_amount}


def checkout(cart, customer, coupon=None):
    """Price a cart and apply an optional coupon.

    Args:
        cart: Iterable of cart items, each with ``sku``, ``price`` and ``qty``.
        customer: Customer mapping whose ``tier`` selects the tier discount.
        coupon: Optional coupon code; ``None`` means no coupon.

    Returns:
        A ``{"lines": [...], "total": Decimal}`` dict.

    Raises:
        ValueError: If a coupon code is not recognised.
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
            total = total - (total * pct / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            raise ValueError("unknown coupon")
    if total < 0:
        total = Decimal("0")
    return {"lines": lines, "total": total.quantize(Decimal("0.01"))}
