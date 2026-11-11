from decimal import Decimal
from pricing import TIER_DISCOUNTS, TAX_RATES, checkout, price_line

D = Decimal


def test_basic():
    r = checkout([{"sku": "A", "price": 10, "qty": 2}], {})
    assert r["total"] == D("23.80")


def test_books_tax():
    r = checkout([{"sku": "B", "price": "12.99", "qty": 1, "category": "books"}], {})
    assert r["lines"][0]["tax"] == D("0.91")
    assert r["total"] == D("13.90")


def test_silver_bulk():
    r = checkout([{"sku": "C", "price": "3.33", "qty": 10}], {"tier": "silver"})
    assert r["lines"][0]["net"] == D("28.47")


def test_coupon_welcome():
    r = checkout([{"sku": "A", "price": 20, "qty": 1}], {}, "WELCOME5")
    assert r["total"] == D("18.80")


def test_discount_and_tax_tables():
    assert TIER_DISCOUNTS == {"silver": D("0.05"), "platinum": D("0.20"), "gold": D("0.12")}
    assert TAX_RATES == {"books": D("0.07"), "food": D("0.07"), "default": D("0.19")}


def test_gold_and_bulk_boundary():
    item = {"sku": "G", "price": "3.33", "qty": 10, "category": "books"}
    assert price_line(item, {"tier": "gold"}) == {"sku": "G", "net": D("26.37"), "tax": D("1.85")}
    assert checkout([item], {"tier": "gold"})["total"] == D("28.22")
    item["qty"] = 9
    assert price_line(item, {"tier": "gold"})["net"] == D("26.37")
    item["qty"] = 1
    assert price_line(item, {"tier": "Gold"})["net"] == D("3.33")


def test_skipped_items():
    for qty in (0, -1):
        item = {"price": 10, "qty": qty}
        assert price_line(item, {}) is None
        assert checkout([item], {}) == {"lines": [], "total": D("0.00")}


def test_rounding_and_defaults():
    item = {"sku": "R", "price": "0.075", "qty": 1}
    assert price_line(item, {}) == {"sku": "R", "net": D("0.08"), "tax": D("0.02")}
    for category in ("books", "food", "Books", "unknown", None, []):
        item["category"] = category
        expected_tax = D("0.01") if category in ("books", "food") else D("0.02")
        assert price_line(item, {"tier": []})["tax"] == expected_tax


def test_coupon_edges():
    cart = [{"sku": "A", "price": 10, "qty": 1}]
    for coupon, expected in (("WELCOME5", "11.90"), ("HALFSHIP", "11.90"),
                             ("PCT50", "8.33"), ("PCT-10", "13.09")):
        assert checkout(cart, {}, coupon)["total"] == D(expected)
    for coupon in ("unknown", "PCT"):
        try:
            checkout(cart, {}, coupon)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid coupon accepted")


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
