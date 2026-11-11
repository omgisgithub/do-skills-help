from datetime import datetime

import pytest

from cronexpr import next_run


# --- spec examples (verbatim) ---

def test_spec_examples():
    assert next_run("*/15 * * * *", datetime(2026, 3, 4, 10, 7)) == datetime(2026, 3, 4, 10, 15)
    assert next_run("0 9 * * MON-FRI", datetime(2026, 3, 6, 9, 0)) == datetime(2026, 3, 9, 9, 0)
    assert next_run("0 0 29 2 *", datetime(2026, 3, 1)) == datetime(2028, 2, 29, 0, 0)
    assert next_run("30 4 1,15 * 5", datetime(2026, 1, 1, 5, 0)) == datetime(2026, 1, 2, 4, 30)


def test_no_match_within_5_years():
    with pytest.raises(ValueError):
        next_run("0 0 30 2 *", datetime(2026, 3, 1))


# --- result rules ---

def test_strictly_later_and_truncated():
    assert next_run("* * * * *", datetime(2026, 3, 4, 12, 0, 30)) == datetime(2026, 3, 4, 12, 1)
    assert next_run("* * * * *", datetime(2026, 3, 4, 12, 0, 0)) == datetime(2026, 3, 4, 12, 1)
    assert next_run("* * * * *", datetime(2026, 3, 4, 12, 0, 0, 5)) == datetime(2026, 3, 4, 12, 1)
    assert next_run("@hourly", datetime(2026, 3, 4, 10, 0)) == datetime(2026, 3, 4, 11, 0)


def test_result_has_zero_seconds():
    result = next_run("5 * * * *", datetime(2026, 3, 4, 10, 30, 45, 123))
    assert (result.second, result.microsecond) == (0, 0)


def test_five_year_boundary_is_inclusive_and_fails_past_it():
    # 2096-03-01 -> next leap day is 2104-02-29, outside 5 years.
    with pytest.raises(ValueError):
        next_run("0 0 29 2 *", datetime(2096, 3, 1))
    # 2024-03-01 -> 2028-02-29 is inside 5 years.
    assert next_run("0 0 29 2 *", datetime(2024, 3, 1)) == datetime(2028, 2, 29)


# --- expression syntax: must pass ---

@pytest.mark.parametrize("expr, after, expected", [
    ("  */15 * * * *  ", datetime(2026, 3, 4, 10, 7), datetime(2026, 3, 4, 10, 15)),
    ("*/15\t*\t*\t*\t*", datetime(2026, 3, 4, 10, 7), datetime(2026, 3, 4, 10, 15)),
    ("5/20 * * * *", datetime(2026, 3, 4, 10, 6), datetime(2026, 3, 4, 10, 25)),
    ("0 0 * * 7", datetime(2026, 3, 7, 23, 0), datetime(2026, 3, 8, 0, 0)),        # 7 = Sunday
    ("0 0 * * 5-7", datetime(2026, 3, 5, 0, 0), datetime(2026, 3, 6, 0, 0)),        # Fri..Sun
    ("0 0 * * 0-7/3", datetime(2026, 3, 1, 0, 0), datetime(2026, 3, 4, 0, 0)),      # 0,3,6
    ("0 0 * * */3", datetime(2026, 3, 1, 0, 0), datetime(2026, 3, 4, 0, 0)),        # 0,3,6
    ("0 0 * * mon-fri", datetime(2026, 3, 6, 9, 0), datetime(2026, 3, 9, 0, 0)),    # lowercase
    ("0 0 * * Mon-Fri", datetime(2026, 3, 6, 9, 0), datetime(2026, 3, 9, 0, 0)),
    ("0 0 1 dec *", datetime(2026, 3, 1), datetime(2026, 12, 1)),
    ("0 0 1 JAN-MAR/2 *", datetime(2026, 2, 2), datetime(2026, 3, 1)),              # 1,3
    ("0 0 */2 * *", datetime(2026, 3, 1, 0, 0), datetime(2026, 3, 3, 0, 0)),        # restricted dom
    ("0 0 13 * FRI", datetime(2026, 3, 2), datetime(2026, 3, 6)),                   # OR rule
    ("0 0 13 * FRI", datetime(2026, 3, 7), datetime(2026, 3, 13)),                  # OR rule
    ("0 0 1-31 * MON", datetime(2026, 3, 2), datetime(2026, 3, 3)),                 # dom 1-31 restricted, OR
    ("0 0 * * 1,3,SUN", datetime(2026, 3, 4), datetime(2026, 3, 8)),
    ("@yearly", datetime(2026, 3, 4), datetime(2027, 1, 1)),
    ("@ANNUALLY", datetime(2026, 3, 4), datetime(2027, 1, 1)),
    ("@monthly", datetime(2026, 3, 15), datetime(2026, 4, 1)),
    ("@weekly", datetime(2026, 3, 4), datetime(2026, 3, 8)),
    ("@Daily", datetime(2026, 3, 4, 1), datetime(2026, 3, 5)),
    ("@midnight", datetime(2026, 3, 4, 1), datetime(2026, 3, 5)),
])
def test_valid_expressions(expr, after, expected):
    assert next_run(expr, after) == expected


# --- expression syntax: must fail ---

@pytest.mark.parametrize("expr", [
    "",
    "* * * *",                  # 4 fields
    "* * * * * *",              # 6 fields
    "60 * * * *",               # minute out of range
    "* 24 * * *",               # hour out of range
    "* * 0 * *",                # dom below 1
    "* * 32 * *",               # dom out of range
    "* * * 0 *",                # month below 1
    "* * * 13 *",               # month out of range
    "* * * * 8",                # dow out of range
    "* * JAN * *",              # month name in dom field
    "* * * MON *",              # dow name in month field
    "0 0 * * JAN",              # month name in dow field
    "* * * JANUARY *",          # unknown name
    "0 0 * * FRI-MON",          # wrap-around range
    "0 0 * * MON-SUN",          # 1-0 is reversed
    "5-3 * * * *",              # reversed range
    "*/0 * * * *",              # step 0
    "1/0 * * * *",
    "*/-1 * * * *",             # negative step
    "*/1.5 * * * *",
    "1,,2 * * * *",             # empty item
    "1, * * * *",               # trailing comma
    ",1 * * * *",
    "1-2-3 * * * *",
    "*-5 * * * *",
    "5-* * * * *",
    "-5 * * * *",
    "5- * * * *",
    "/5 * * * *",
    "5/ * * * *",
    "+5 * * * *",
    "1.0 * * * *",
    "a * * * *",
    "*/15\n* * * *",            # newline inside expression
    "1 , 2 * * *",              # spaces around comma -> extra field
    "@reboot",
    "@every 5m",
    "@YEARLY2",
])
def test_invalid_expressions(expr):
    with pytest.raises(ValueError):
        next_run(expr, datetime(2026, 3, 4, 10, 7))


@pytest.mark.parametrize("expr", [None, 5, b"* * * * *", ["* * * * *"]])
def test_non_str_expr_is_type_error(expr):
    with pytest.raises(TypeError):
        next_run(expr, datetime(2026, 3, 4, 10, 7))
