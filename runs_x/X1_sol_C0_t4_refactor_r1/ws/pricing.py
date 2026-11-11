# Checkout pricing preserves the legacy order of discounts and rounding.
from decimal import Decimal, ROUND_HALF_UP, localcontext


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
    p = Decimal(str(item["price"]))
    q = item["qty"]
    if q <= 0:
        return None

    # Equality lookups also accept unhashable tier/category values, as before.
    discount = next((rate for tier, rate in TIER_DISCOUNTS.items()
                     if customer.get("tier") == tier), None)
    line = p * q
    if q >= 10:
        line = line * Decimal("0.9")
    if discount is not None:
        # Construct the legacy multiplier exactly, even at low caller precision.
        with localcontext() as context:
            context.prec = max(context.prec, 28)
            multiplier = Decimal("1.00") - discount
        line = line * multiplier

    tax = next((rate for category, rate in TAX_RATES.items()
                if category != "default" and item.get("category") == category),
               TAX_RATES["default"])
    line = line.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    t = (line * tax).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"sku": item["sku"], "net": line, "tax": t}


def checkout(cart, customer, coupon=None):
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
