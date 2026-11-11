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


def test_rate_tables():
    assert TIER_DISCOUNTS == {
        "silver": D("0.05"), "platinum": D("0.20"), "gold": D("0.12")
    }
    assert TAX_RATES == {
        "books": D("0.07"), "food": D("0.07"), "default": D("0.19")
    }


def test_gold_and_bulk_boundary():
    for qty, net, tax in [(1, "2.93", "0.56"), (9, "26.37", "5.01"),
                          (10, "26.37", "5.01")]:
        item = {"sku": "G", "price": "3.33", "qty": qty}
        expected = {"sku": "G", "net": D(net), "tax": D(tax)}
        assert price_line(item, {"tier": "gold"}) == expected
        assert checkout([item], {"tier": "gold"}) == {
            "lines": [expected], "total": D(net) + D(tax)
        }


def test_line_rounding_and_tax_defaults():
    for category, tax in [("books", "0.01"), ("food", "0.01"),
                          (None, "0.03"), ("BOOKS", "0.03"),
                          ([], "0.03"), ("default", "0.03")]:
        item = {"sku": "R", "price": "0.145", "qty": 1,
                "category": category}
        assert price_line(item, {}) == {
            "sku": "R", "net": D("0.15"), "tax": D(tax)
        }
    for tier in [None, "unknown", "GOLD", []]:
        assert price_line({"sku": "A", "price": 10, "qty": 1},
                          {"tier": tier})["net"] == D("10.00")


def test_skipped_items_and_conversion_order():
    for qty in [0, -1]:
        item = {"price": 1, "qty": qty}
        assert price_line(item, {}) is None
        assert checkout([item], {}) == {"lines": [], "total": D("0.00")}
    try:
        price_line({"price": "bad", "qty": 0}, {})
    except InvalidOperation:
        pass
    else:
        raise AssertionError("Invalid prices must fail even for skipped items")


def test_coupon_edges_and_line_order():
    cart = [{"sku": "A", "price": 10, "qty": 1},
            {"sku": "skip", "price": 10, "qty": 0},
            {"sku": "B", "price": 10, "qty": 1}]
    assert [line["sku"] for line in checkout(cart, {})["lines"]] == ["A", "B"]
    for coupon, total in [("WELCOME5", "18.80"), ("HALFSHIP", "23.80"),
                          ("PCT50", "16.66"), ("PCT-10", "26.18")]:
        assert checkout(cart, {}, coupon)["total"] == D(total)
    assert checkout(cart[:1], {}, "WELCOME5")["total"] == D("11.90")
    assert checkout([{"sku": "N", "price": -1, "qty": 1}], {})["total"] == D("0.00")
    for coupon in ["unknown", "PCTbad"]:
        try:
            checkout(cart, {}, coupon)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid coupon must fail")


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
