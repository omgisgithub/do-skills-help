from decimal import Decimal
from pricing import checkout, price_line

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


def test_gold_discount():
    r = checkout([{"sku": "D", "price": "10.00", "qty": 1}], {"tier": "gold"})
    assert r["lines"][0]["net"] == D("8.80")
    assert r["total"] == D("10.47")


def test_gold_bulk():
    r = checkout([{"sku": "E", "price": "10.00", "qty": 10}], {"tier": "gold"})
    assert r["lines"][0]["net"] == D("79.20")


def test_price_line_non_positive_qty_returns_none():
    assert price_line({"sku": "F", "price": "10.00", "qty": 0}, {}) is None
    assert price_line({"sku": "G", "price": "10.00", "qty": -1}, {}) is None


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
