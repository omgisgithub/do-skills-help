from decimal import Decimal
from pricing import checkout, price_line, TIER_DISCOUNTS, TAX_RATES

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


def test_gold_bulk_and_coupon():
    item = {"sku": "G", "price": "3.33", "qty": 10, "category": "books"}
    assert TIER_DISCOUNTS["gold"] == D("0.12")
    assert price_line(item, {"tier": "gold"}) == {
        "sku": "G", "net": D("26.37"), "tax": D("1.85")}
    assert checkout([item], {"tier": "gold"}, "PCT10")["total"] == D("25.40")


def test_line_rounding_before_tax():
    item = {"sku": "R", "price": "0.024", "qty": 1}
    assert price_line(item, {}) == {
        "sku": "R", "net": D("0.02"), "tax": D("0.00")}
    assert TAX_RATES["default"] == D("0.19")


def test_skipped_items_and_unknown_values():
    assert price_line({"price": 10, "qty": 0}, {}) is None
    assert price_line({"price": 10, "qty": -1}, {}) is None
    item = {"sku": "U", "price": 10, "qty": 1, "category": []}
    assert checkout([item], {"tier": []})["total"] == D("11.90")


def test_coupon_legacy_edges():
    item = {"sku": "C", "price": 20, "qty": 1}
    assert checkout([item], {}, "PCT99")["total"] == D("16.66")
    assert checkout([item], {}, "PCT-10")["total"] == D("26.18")
    assert checkout([item], {}, "HALFSHIP")["total"] == D("23.80")
    assert checkout([dict(item, price=-20)], {})["total"] == D("0.00")


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
