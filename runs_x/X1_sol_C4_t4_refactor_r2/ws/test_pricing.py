from decimal import Decimal, InvalidOperation

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


def test_gold_discount() -> None:
    r = checkout([{"sku": "G", "price": 10, "qty": 2}], {"tier": "gold"})

    assert r == {
        "lines": [{"sku": "G", "net": D("17.60"), "tax": D("3.34")}],
        "total": D("20.94"),
    }


def test_gold_bulk_coupon() -> None:
    r = checkout(
        [{"sku": "G", "price": "3.33", "qty": 10, "category": "food"}],
        {"tier": "gold"},
        "PCT10",
    )

    assert r["lines"] == [{"sku": "G", "net": D("26.37"), "tax": D("1.85")}]
    assert r["total"] == D("25.40")


def test_price_line_platinum_rounds_net_before_tax() -> None:
    r = price_line({"sku": "P", "price": "0.045", "qty": 1}, {"tier": "platinum"})

    assert r == {"sku": "P", "net": D("0.04"), "tax": D("0.01")}


def test_price_line_rounds_half_up() -> None:
    r = price_line({"sku": "R", "price": "1.005", "qty": 1}, {})

    assert r == {"sku": "R", "net": D("1.01"), "tax": D("0.19")}


def test_nonpositive_quantities_skip_without_sku() -> None:
    cart = [{"price": 10, "qty": 0}, {"price": 10, "qty": -1}]

    assert price_line(cart[0], {"tier": "gold"}) is None
    assert checkout(cart, {"tier": "gold"}) == {"lines": [], "total": D("0.00")}


def test_skipped_quantity_still_validates_price() -> None:
    try:
        price_line({"price": "invalid", "qty": 0}, {})
    except InvalidOperation:
        return
    raise AssertionError("Legacy price conversion must precede quantity filtering")


def test_unknown_unhashable_tier_and_category_use_defaults() -> None:
    r = checkout([{"sku": "U", "price": 10, "qty": 1, "category": []}], {"tier": []})

    assert r["total"] == D("11.90")


def test_checkout_preserves_line_order_and_individual_rounding() -> None:
    cart = [{"sku": sku, "price": "0.025", "qty": 1} for sku in ("B", "A")]

    r = checkout(cart, {})

    assert [line["sku"] for line in r["lines"]] == ["B", "A"]
    assert r["total"] == D("0.08")


def test_coupons_preserve_caps_negative_percent_and_noop() -> None:
    cart = [{"sku": "A", "price": 20, "qty": 1}]

    assert checkout(cart, {}, "HALFSHIP")["total"] == D("23.80")
    assert checkout(cart, {}, "PCT99")["total"] == D("16.66")
    assert checkout(cart, {}, "PCT-10")["total"] == D("26.18")
    assert checkout([], {}, "WELCOME5")["total"] == D("0.00")


def test_unknown_and_malformed_coupons_raise() -> None:
    for coupon in ("UNKNOWN", "PCT", "PCTbad"):
        try:
            checkout([], {"tier": "gold"}, coupon)
        except ValueError:
            continue
        raise AssertionError("Invalid coupons must raise ValueError")


def test_negative_total_clamped_without_changing_lines() -> None:
    r = checkout([{"sku": "N", "price": -10, "qty": 1}], {})

    assert r["lines"] == [{"sku": "N", "net": D("-10.00"), "tax": D("-1.90")}]
    assert r["total"] == D("0.00")


def test_rate_tables_contain_decimal_fractions() -> None:
    assert TIER_DISCOUNTS == {"silver": D("0.05"), "platinum": D("0.20"), "gold": D("0.12")}
    assert TAX_RATES == {"books": D("0.07"), "food": D("0.07"), "default": D("0.19")}


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
