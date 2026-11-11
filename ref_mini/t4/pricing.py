from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")
TIER_DISCOUNTS = {"silver": Decimal("0.05"), "gold": Decimal("0.12"), "platinum": Decimal("0.20")}
TAX_RATES = {"books": Decimal("0.07"), "food": Decimal("0.07"), "default": Decimal("0.19")}
BULK_QTY = 10
BULK_FACTOR = Decimal("0.9")


def _r(x):
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def price_line(item, customer):
    q = item["qty"]
    if q <= 0:
        return None
    line = Decimal(str(item["price"])) * q
    if q >= BULK_QTY:
        line = line * BULK_FACTOR
    disc = TIER_DISCOUNTS.get(customer.get("tier"))
    if disc is not None:
        line = line * (1 - disc)
    line = _r(line)
    rate = TAX_RATES.get(item.get("category"), TAX_RATES["default"])
    return {"sku": item["sku"], "net": line, "tax": _r(line * rate)}


def _apply_coupon(total, coupon):
    if coupon is None or coupon == "HALFSHIP":
        return total
    if coupon == "WELCOME5":
        return total - 5 if total >= 20 else total
    if coupon.startswith("PCT"):
        pct = min(int(coupon[3:]), 30)
        return total - _r(total * pct / 100)
    raise ValueError("unknown coupon")


def checkout(cart, customer, coupon=None):
    lines = [l for l in (price_line(i, customer) for i in cart) if l is not None]
    total = sum((l["net"] + l["tax"] for l in lines), Decimal("0"))
    total = max(_apply_coupon(total, coupon), Decimal("0"))
    return {"lines": lines, "total": total.quantize(CENT)}
