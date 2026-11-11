import random
import subprocess
import sys
from decimal import Decimal, ROUND_HALF_UP
import pricing

D = Decimal
TIERS = {"silver": D("0.95"), "gold": D("0.88"), "platinum": D("0.80")}


def legacy(cart, customer, coupon=None):
    # the original algorithm, written out once, plus gold at 12%
    total = D("0")
    lines = []
    for item in cart:
        p = D(str(item["price"]))
        q = item["qty"]
        if q <= 0:
            continue
        line = p * q
        if q >= 10:
            line = line * D("0.9")
        f = TIERS.get(customer.get("tier"))
        if f is not None:
            line = line * f
        tax = D("0.07") if item.get("category") in ("books", "food") else D("0.19")
        line = line.quantize(D("0.01"), rounding=ROUND_HALF_UP)
        t = (line * tax).quantize(D("0.01"), rounding=ROUND_HALF_UP)
        lines.append({"sku": item["sku"], "net": line, "tax": t})
        total = total + line + t
    if coupon is not None:
        if coupon == "WELCOME5":
            if total >= D("20"):
                total = total - D("5")
        elif coupon == "HALFSHIP":
            pass
        elif coupon.startswith("PCT"):
            pct = int(coupon[3:])
            if pct > 30:
                pct = 30
            total = total - (total * pct / 100).quantize(D("0.01"), rounding=ROUND_HALF_UP)
        else:
            raise ValueError("unknown coupon")
    if total < 0:
        total = D("0")
    return {"lines": lines, "total": total.quantize(D("0.01"))}


def norm(r):
    return ([(l["sku"], l["net"], l["tax"]) for l in r["lines"]], r["total"])


def outcome(fn, *a):
    try:
        return ("ok", norm(fn(*a)))
    except ValueError:
        return ("ValueError",)


def rand_cart(rng):
    cart = []
    for i in range(rng.randint(0, 6)):
        price = rng.choice([rng.randint(1, 5000) / 100, rng.randint(1, 300), "19.99", 0.1, 2.675, 1.005])
        cart.append({"sku": "S%d" % i, "price": price, "qty": rng.choice([0, -1, 1, 2, 3, 9, 10, 11, 13, 17, 25]),
                     **({"category": rng.choice(["books", "food", "toys", "Books", None])} if rng.random() < .8 else {})})
    return cart


def test_matches_legacy_random():
    rng = random.Random(2026)
    for _ in range(4000):
        cart = rand_cart(rng)
        cust = rng.choice([{}, {"tier": "silver"}, {"tier": "gold"}, {"tier": "platinum"}, {"tier": "bronze"}, {"tier": None}])
        coupon = rng.choice([None, "WELCOME5", "HALFSHIP", "PCT10", "PCT30", "PCT45", "PCT0", "FREE", "PCT7"])
        a, b = outcome(pricing.checkout, cart, cust, coupon), outcome(legacy, cart, cust, coupon)
        assert a == b, (cart, cust, coupon, a, b)


def test_gold():
    r = pricing.checkout([{"sku": "G", "price": "3.33", "qty": 10}], {"tier": "gold"})
    assert r["lines"][0]["net"] == D("26.37"), r


def test_structure():
    assert pricing.TIER_DISCOUNTS["silver"] == D("0.05")
    assert pricing.TIER_DISCOUNTS["gold"] == D("0.12")
    assert pricing.TIER_DISCOUNTS["platinum"] == D("0.20")
    assert pricing.TAX_RATES["default"] == D("0.19")
    assert pricing.TAX_RATES["books"] == D("0.07") and pricing.TAX_RATES["food"] == D("0.07")
    assert pricing.price_line({"sku": "x", "price": 1, "qty": 0}, {}) is None
    l = pricing.price_line({"sku": "x", "price": "12.99", "qty": 1, "category": "books"}, {})
    assert l["sku"] == "x" and l["net"] == D("12.99") and l["tax"] == D("0.91")


def test_tables_are_used():
    old = dict(pricing.TIER_DISCOUNTS)
    try:
        pricing.TIER_DISCOUNTS["diamond"] = D("0.50")
        r = pricing.checkout([{"sku": "A", "price": 10, "qty": 1}], {"tier": "diamond"})
        assert r["lines"][0]["net"] == D("5.00"), r
    finally:
        pricing.TIER_DISCOUNTS.clear()
        pricing.TIER_DISCOUNTS.update(old)


def test_visible_tests_still_pass():
    p = subprocess.run([sys.executable, "test_pricing.py"], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-1500:]


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as e:
                fails += 1
                print("FAIL", name, type(e).__name__, str(e)[:600])
    sys.exit(1 if fails else 0)
