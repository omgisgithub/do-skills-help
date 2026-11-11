"""Checkout pricing with per-line discounts and tax rounding."""
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

    line = p * q
    if q >= 10:
        line = line * Decimal("0.9")
    # Equality comparisons retain the legacy fallback for unhashable values.
    for tier, discount in TIER_DISCOUNTS.items():
        if customer.get("tier") == tier:
            # Form the exact multiplier even under a low-precision context;
            # apply it using the caller's context, as the legacy code did.
            with localcontext() as context:
                context.prec = max(context.prec, 2)
                multiplier = Decimal("1.00") - discount
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
