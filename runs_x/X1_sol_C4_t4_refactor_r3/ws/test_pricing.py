from decimal import Decimal, InvalidOperation
from unittest import TestCase
from pricing import TAX_RATES, TIER_DISCOUNTS, checkout, price_line

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


def test_gold_bulk_coupon() -> None:
    result = checkout([{"sku": "G", "price": "3.33", "qty": 10}], {"tier": "gold"}, "WELCOME5")

    assert TIER_DISCOUNTS["gold"] == D("0.12")
    assert result == {
        "lines": [{"sku": "G", "net": D("26.37"), "tax": D("5.01")}],
        "total": D("26.38"),
    }


def test_gold_books() -> None:
    result = price_line({"sku": "G", "price": "12.99", "qty": 1, "category": "books"}, {"tier": "gold"})

    assert result == {"sku": "G", "net": D("11.43"), "tax": D("0.80")}


def test_discount_rounding_order() -> None:
    result = price_line({"sku": "R", "price": "0.045", "qty": 10}, {"tier": "silver"})

    assert result == {"sku": "R", "net": D("0.38"), "tax": D("0.07")}


def test_tax_uses_rounded_net() -> None:
    result = price_line({"sku": "R", "price": "0.0249", "qty": 1}, {})

    assert result == {"sku": "R", "net": D("0.02"), "tax": D("0.00")}


def test_platinum_food() -> None:
    result = price_line({"sku": "P", "price": 10, "qty": 1, "category": "food"}, {"tier": "platinum"})

    assert result == {"sku": "P", "net": D("8.00"), "tax": D("0.56")}


def test_unhashable_tier_and_category_use_defaults() -> None:
    result = price_line({"sku": "U", "price": 10, "qty": 1, "category": []}, {"tier": []})

    assert TAX_RATES["default"] == D("0.19")
    assert result == {"sku": "U", "net": D("10.00"), "tax": D("1.90")}


def test_nonpositive_quantity_skips_missing_sku() -> None:
    assert price_line({"price": 10, "qty": 0}, {}) is None
    assert price_line({"price": 10, "qty": -1}, {}) is None
    assert checkout([{"price": 10, "qty": 0}], {}) == {"lines": [], "total": D("0.00")}


def test_skipped_quantity_still_validates_price() -> None:
    with TestCase().assertRaises(InvalidOperation):
        price_line({"price": "invalid", "qty": 0}, {})


def test_percentage_coupon_cap_and_negative_percentage() -> None:
    cart = [{"sku": "A", "price": 20, "qty": 1}]

    assert checkout(cart, {}, "PCT99")["total"] == D("16.66")
    assert checkout(cart, {}, "PCT-10")["total"] == D("26.18")
    assert checkout(cart, {}, "HALFSHIP")["total"] == D("23.80")


def test_coupon_errors_are_preserved() -> None:
    with TestCase().assertRaises(ValueError):
        checkout([], {}, "unknown")
    with TestCase().assertRaises(ValueError):
        checkout([], {}, "PCTbad")


def test_negative_total_clamped_after_line_pricing() -> None:
    result = checkout([{"sku": "N", "price": -10, "qty": 1}], {})

    assert result == {
        "lines": [{"sku": "N", "net": D("-10.00"), "tax": D("-1.90")}],
        "total": D("0.00"),
    }


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
