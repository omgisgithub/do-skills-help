# legacy checkout pricing. DO NOT TOUCH (written 2019, nobody knows why it works)
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


def _discount(customer):
    tier = customer.get("tier")
    if not isinstance(tier, str):
        return Decimal("0")
    return TIER_DISCOUNTS.get(tier, Decimal("0"))


def _tax_rate(item):
    category = item.get("category")
    if isinstance(category, str) and category in TAX_RATES:
        return TAX_RATES[category]
    return TAX_RATES["default"]


def price_line(item, customer):
    p = Decimal(str(item["price"]))
    q = item["qty"]
    if q <= 0:
        return None
    line = p * q
    if q >= 10:
        line = line * Decimal("0.9")
    line = line * (Decimal("1") - _discount(customer))
    line = line.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    t = (line * _tax_rate(item)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
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
