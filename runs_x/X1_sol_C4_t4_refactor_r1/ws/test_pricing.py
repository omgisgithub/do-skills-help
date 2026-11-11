from decimal import Decimal, Inexact, InvalidOperation, localcontext
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


def test_gold_bulk_and_tax_rounding() -> None:
    result = checkout([{"sku": "G", "price": "3.33", "qty": 10}], {"tier": "gold"})

    assert TIER_DISCOUNTS["gold"] == D("0.12")
    assert result == {
        "lines": [{"sku": "G", "net": D("26.37"), "tax": D("5.01")}],
        "total": D("31.38"),
    }


def test_gold_coupon_applies_after_tax() -> None:
    result = checkout([{"sku": "G", "price": 20, "qty": 1}], {"tier": "gold"}, "WELCOME5")

    assert result["total"] == D("15.94")


def test_price_line_rounds_net_before_tax() -> None:
    result = price_line({"sku": "R", "price": "0.025", "qty": 1}, {})

    assert result == {"sku": "R", "net": D("0.03"), "tax": D("0.01")}


def test_price_line_skips_nonpositive_quantities() -> None:
    assert price_line({"price": 10, "qty": 0}, {"tier": "gold"}) is None
    assert price_line({"price": 10, "qty": -1}, {}) is None


def test_price_line_invalid_price_still_raises_for_zero_quantity() -> None:
    try:
        price_line({"price": "invalid", "qty": 0}, {})
    except InvalidOperation:
        return
    raise AssertionError("Expected invalid price conversion to fail")


def test_unknown_unhashable_tier_and_category_use_defaults() -> None:
    result = price_line({"sku": "U", "price": 10, "qty": 1, "category": []}, {"tier": []})

    assert TAX_RATES["default"] == D("0.19")
    assert result == {"sku": "U", "net": D("10.00"), "tax": D("1.90")}


def test_food_platinum_bulk_discount() -> None:
    result = price_line(
        {"sku": "F", "price": "3.33", "qty": 10, "category": "food"},
        {"tier": "platinum"},
    )

    assert result == {"sku": "F", "net": D("23.98"), "tax": D("1.68")}


def test_checkout_keeps_line_order_and_per_line_rounding() -> None:
    result = checkout(
        [{"sku": sku, "price": "0.025", "qty": 1} for sku in ("B", "A")], {}
    )

    assert [line["sku"] for line in result["lines"]] == ["B", "A"]
    assert result["total"] == D("0.08")


def test_percentage_coupons_keep_cap_and_negative_values() -> None:
    cart = [{"sku": "C", "price": 10, "qty": 1}]

    assert checkout(cart, {}, "PCT99")["total"] == D("8.33")
    assert checkout(cart, {}, "PCT-10")["total"] == D("13.09")
    assert checkout(cart, {}, "HALFSHIP")["total"] == D("11.90")


def test_gold_unknown_coupon_raises() -> None:
    try:
        checkout([], {"tier": "gold"}, "unknown")
    except ValueError as exc:
        assert str(exc) == "unknown coupon"
        return
    raise AssertionError("Expected an unknown coupon to fail")


def test_negative_total_is_clamped_without_changing_lines() -> None:
    result = checkout([{"sku": "N", "price": -10, "qty": 1}], {})

    assert result["lines"][0]["net"] == D("-10.00")
    assert result["total"] == D("0.00")


def test_tier_multiplier_preserves_low_precision_context() -> None:
    with localcontext() as context:
        context.prec = 1
        context.traps[Inexact] = True

        result = checkout([{"sku": "Z", "price": 0, "qty": 1}], {"tier": "silver"})

        assert result["total"] == D("0.00")


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
