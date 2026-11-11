# legacy checkout pricing. DO NOT TOUCH (written 2019, nobody knows why it works)
from decimal import Decimal, ROUND_HALF_UP


def checkout(cart, customer, coupon=None):
    total = Decimal("0")
    lines = []
    for item in cart:
        p = Decimal(str(item["price"]))
        q = item["qty"]
        if q <= 0:
            continue
        if customer.get("tier") == "silver":
            if item.get("category") == "books":
                line = p * q
                if q >= 10:
                    line = line * Decimal("0.9")
                line = line * Decimal("0.95")
            else:
                line = p * q
                if q >= 10:
                    line = line * Decimal("0.9")
                line = line * Decimal("0.95")
        elif customer.get("tier") == "platinum":
            if item.get("category") == "books":
                line = p * q
                if q >= 10:
                    line = line * Decimal("0.9")
                line = line * Decimal("0.80")
            else:
                line = p * q
                if q >= 10:
                    line = line * Decimal("0.9")
                line = line * Decimal("0.80")
        else:
            if item.get("category") == "books":
                line = p * q
                if q >= 10:
                    line = line * Decimal("0.9")
            else:
                line = p * q
                if q >= 10:
                    line = line * Decimal("0.9")
        if item.get("category") == "books":
            tax = Decimal("0.07")
        elif item.get("category") == "food":
            tax = Decimal("0.07")
        else:
            tax = Decimal("0.19")
        line = line.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        t = (line * tax).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        lines.append({"sku": item["sku"], "net": line, "tax": t})
        total = total + line + t
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
