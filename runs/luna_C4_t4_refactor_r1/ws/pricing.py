# legacy checkout pricing. Preserve the established rounding and discount order.
from decimal import Decimal, ROUND_HALF_UP


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


def price_line(item, customer):
    """Price one cart item, returning no line when its quantity is not positive."""
    quantity = item["qty"]
    if quantity <= 0:
        return None

    price = Decimal(str(item["price"]))
    line = price * quantity
    if quantity >= 10:
        line = line * Decimal("0.9")

    discount = TIER_DISCOUNTS.get(customer.get("tier"), Decimal("0"))
    if discount:
        line = line * (Decimal("1") - discount)

    category = item.get("category")
    tax_rate = TAX_RATES.get(category, TAX_RATES["default"])
    line = line.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    tax = (line * tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"sku": item["sku"], "net": line, "tax": tax}


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
            total = total - (total * pct / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            raise ValueError("unknown coupon")
    if total < 0:
        total = Decimal("0")
    return {"lines": lines, "total": total.quantize(Decimal("0.01"))}
