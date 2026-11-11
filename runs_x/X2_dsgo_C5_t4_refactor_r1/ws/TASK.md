# Refactor checkout pricing, then add a tier

`pricing.py` has one long `checkout()` function full of copy-paste. Product wants a new
customer tier, and nobody wants to add a fourth copy of the block.

1. Refactor `pricing.py` so that:
   - tier discounts live in one module-level dict `TIER_DISCOUNTS` mapping tier name to the
     discount as a `Decimal` fraction (e.g. silver → `Decimal("0.05")`);
   - tax rates live in one module-level dict `TAX_RATES` mapping category to rate, with the
     default rate used for any other/missing category stored under the key `"default"`;
   - there is a function `price_line(item, customer)` that returns the
     `{"sku", "net", "tax"}` dict for one cart item (or `None` for items with qty <= 0);
   - `checkout(cart, customer, coupon=None)` uses `price_line` and keeps exactly the same
     signature and **exactly the same results** as today for every input — including all the
     odd details of rounding and ordering of discounts. Existing callers rely on them.
2. Add a new tier `"gold"` with a 12% discount, behaving exactly like the other tiers.

`test_pricing.py` must keep passing (`python3 test_pricing.py`). Python 3.9, stdlib only.
