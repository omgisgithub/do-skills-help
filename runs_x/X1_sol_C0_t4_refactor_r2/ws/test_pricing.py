from decimal import Decimal
from pricing import checkout, price_line, TAX_RATES, TIER_DISCOUNTS

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
    customer = {"tier": "gold"}
    assert TIER_DISCOUNTS["gold"] == D("0.12")
    assert price_line(item, customer) == {
        "sku": "G", "net": D("26.37"), "tax": D("1.85")
    }
    assert checkout([item], customer, "PCT10")["total"] == D("25.40")


def test_round_each_line_before_tax_and_coupon():
    item = {"sku": "R", "price": "0.025", "qty": 1}
    result = checkout([item, item], {}, "PCT30")
    assert result["lines"] == [
        {"sku": "R", "net": D("0.03"), "tax": D("0.01")}
    ] * 2
    assert result["total"] == D("0.06")


def test_skipped_quantity_and_unknown_values():
    assert price_line({"price": 1, "qty": 0}, {}) is None
    assert price_line({"price": 1, "qty": -1}, {}) is None
    assert TAX_RATES["default"] == D("0.19")
    assert price_line(
        {"sku": "U", "price": 10, "qty": 1, "category": []}, {"tier": []}
    ) == {"sku": "U", "net": D("10.00"), "tax": D("1.90")}


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
