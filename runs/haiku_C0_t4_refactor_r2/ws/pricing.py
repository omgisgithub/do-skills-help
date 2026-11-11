# legacy checkout pricing. DO NOT TOUCH (written 2019, nobody knows why it works)
from decimal import Decimal, ROUND_HALF_UP

TIER_DISCOUNTS = {
    "silver": Decimal("0.05"),
    "gold": Decimal("0.12"),
    "platinum": Decimal("0.20"),
}

TAX_RATES = {
    "books": Decimal("0.07"),
    "food": Decimal("0.07"),
    "default": Decimal("0.19"),
}

CENT = Decimal("0.01")


def price_line(item, customer):
    p = Decimal(str(item["price"]))
    q = item["qty"]
    if q <= 0:
        return None
    line = p * q
    if q >= 10:
        line = line * Decimal("0.9")
    tier = customer.get("tier")
    if isinstance(tier, str) and tier in TIER_DISCOUNTS:
        line = line * (Decimal("1") - TIER_DISCOUNTS[tier])
    category = item.get("category")
    if not isinstance(category, str) or category not in TAX_RATES:
        category = "default"
    line = line.quantize(CENT, rounding=ROUND_HALF_UP)
    tax = (line * TAX_RATES[category]).quantize(CENT, rounding=ROUND_HALF_UP)
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
