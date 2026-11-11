# legacy checkout pricing, refactored. DO NOT TOUCH (written 2019, nobody knows why it works)
from decimal import Decimal, ROUND_HALF_UP

# Tier name -> discount as a Decimal fraction of the line subtotal.
TIER_DISCOUNTS = {
    "silver": Decimal("0.05"),
    "platinum": Decimal("0.20"),
    "gold": Decimal("0.12"),
}

# Category -> tax rate. "default" applies to any other/missing category.
TAX_RATES = {
    "books": Decimal("0.07"),
    "food": Decimal("0.07"),
    "default": Decimal("0.19"),
}

_BULK_QTY = 10
_BULK_DISCOUNT = Decimal("0.10")
_NO_DISCOUNT = Decimal("0")
_CENT = Decimal("0.01")


def price_line(item, customer):
    """Return the priced line for one cart item, or None when qty <= 0."""
    p = Decimal(str(item["price"]))
    q = item["qty"]
    if q <= 0:
        return None

    line = p * q
    if q >= _BULK_QTY:
        line = line * (Decimal("1") - _BULK_DISCOUNT)

    discount = TIER_DISCOUNTS.get(customer.get("tier"), _NO_DISCOUNT)
    if discount != _NO_DISCOUNT:
        line = line * (Decimal("1") - discount)

    tax = TAX_RATES.get(item.get("category"), TAX_RATES["default"])
    line = line.quantize(_CENT, rounding=ROUND_HALF_UP)
    t = (line * tax).quantize(_CENT, rounding=ROUND_HALF_UP)
    return {"sku": item["sku"], "net": line, "tax": t}


def checkout(cart, customer, coupon=None):
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
            total = total - (total * pct / 100).quantize(_CENT, rounding=ROUND_HALF_UP)
        else:
            raise ValueError("unknown coupon")
    if total < 0:
        total = Decimal("0")
    return {"lines": lines, "total": total.quantize(_CENT)}
