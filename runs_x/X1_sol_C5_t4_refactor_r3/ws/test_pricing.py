from decimal import Decimal
from pricing import checkout

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
    r = checkout([{"sku": "G", "price": "3.33", "qty": 10}],
                 {"tier": "gold"}, "PCT10")
    assert r == {"lines": [{"sku": "G", "net": D("26.37"),
                            "tax": D("5.01")}], "total": D("28.24")}


def test_price_line_rounds_net_before_tax():
    from pricing import price_line

    assert price_line({"sku": "R", "price": "0.065", "qty": 1}, {}) == {
        "sku": "R", "net": D("0.07"), "tax": D("0.01")}
    assert price_line({"price": "1", "qty": 0}, {}) is None
    assert price_line({"price": "1", "qty": -1}, {}) is None


def test_unhashable_tier_and_category_use_defaults():
    r = checkout([{"sku": "U", "price": 10, "qty": 1, "category": []}],
                 {"tier": []})
    assert r == {"lines": [{"sku": "U", "net": D("10.00"),
                            "tax": D("1.90")}], "total": D("11.90")}


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
