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


def test_rate_tables():
    assert TIER_DISCOUNTS == {
        "silver": D("0.05"), "platinum": D("0.20"), "gold": D("0.12")
    }
    assert TAX_RATES == {
        "books": D("0.07"), "food": D("0.07"), "default": D("0.19")
    }


def test_gold_bulk_and_coupon():
    r = checkout([{"sku": "G", "price": "3.33", "qty": 10}],
                 {"tier": "gold"}, "WELCOME5")
    assert r == {"lines": [{"sku": "G", "net": D("26.37"),
                            "tax": D("5.01")}], "total": D("26.38")}
    assert price_line({"sku": "G", "price": 10, "qty": 1,
                       "category": "food"}, {"tier": "gold"}) == {
        "sku": "G", "net": D("8.80"), "tax": D("0.62")
    }


def test_line_rounding_and_fallbacks():
    for category in (None, "unknown", "Books", []):
        assert price_line({"sku": "R", "price": "0.025", "qty": 1,
                           "category": category}, {"tier": []}) == {
            "sku": "R", "net": D("0.03"), "tax": D("0.01")
        }
    for qty in (0, -1):
        assert price_line({"price": 1, "qty": qty}, {}) is None
    # Legacy conversion happens before the quantity check.
    try:
        price_line({"price": "invalid", "qty": 0}, {})
    except ArithmeticError:
        pass
    else:
        raise AssertionError("invalid prices must still fail on skipped items")


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
