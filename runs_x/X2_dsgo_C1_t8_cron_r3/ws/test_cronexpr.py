from datetime import datetime

from cronexpr import next_run

# Spec examples, verbatim.
assert next_run("*/15 * * * *", datetime(2026, 3, 4, 10, 7)) == datetime(2026, 3, 4, 10, 15)
assert next_run("0 9 * * MON-FRI", datetime(2026, 3, 6, 9, 0)) == datetime(2026, 3, 9, 9, 0)
assert next_run("0 0 29 2 *", datetime(2026, 3, 1)) == datetime(2028, 2, 29, 0, 0)
assert next_run("30 4 1,15 * 5", datetime(2026, 1, 1, 5, 0)) == datetime(2026, 1, 2, 4, 30)

# Strictly later than `after`, seconds are discarded.
assert next_run("* * * * *", datetime(2026, 3, 4, 12, 0, 0)) == datetime(2026, 3, 4, 12, 1)
assert next_run("* * * * *", datetime(2026, 3, 4, 12, 0, 30)) == datetime(2026, 3, 4, 12, 1)
assert next_run("* * * * *", datetime(2026, 3, 4, 12, 0, 0, 999999)) == datetime(2026, 3, 4, 12, 1)
assert next_run("* * * * *", datetime(2026, 3, 4, 23, 59, 30)) == datetime(2026, 3, 5, 0, 0)

# Shortcuts, case-insensitive, surrounding whitespace.
assert next_run("@yearly", datetime(2026, 3, 1)) == datetime(2027, 1, 1, 0, 0)
assert next_run("@ANNUALLY", datetime(2026, 3, 1)) == datetime(2027, 1, 1, 0, 0)
assert next_run("  @monthly\t", datetime(2026, 1, 2)) == datetime(2026, 2, 1, 0, 0)
assert next_run("@weekly", datetime(2026, 3, 4)) == datetime(2026, 3, 8, 0, 0)  # Sunday
assert next_run("@daily", datetime(2026, 3, 4, 5, 0)) == datetime(2026, 3, 5, 0, 0)
assert next_run("@midnight", datetime(2026, 3, 4, 5, 0)) == datetime(2026, 3, 5, 0, 0)
assert next_run("@hourly", datetime(2026, 3, 4, 5, 30)) == datetime(2026, 3, 4, 6, 0)

# Names, case-insensitive, ranges.
assert next_run("0 9 * * mon-fri", datetime(2026, 3, 4, 10, 0)) == datetime(2026, 3, 5, 9, 0)
assert next_run("0 0 1 jan-mar *", datetime(2026, 2, 1)) == datetime(2026, 3, 1, 0, 0)
assert next_run("0 0 1 JAN,MAR *", datetime(2026, 2, 1)) == datetime(2026, 3, 1, 0, 0)

# Steps on *, ranges, and single values.
assert next_run("*/15 * * * *", datetime(2026, 3, 4, 10, 0)) == datetime(2026, 3, 4, 10, 15)
assert next_run("5/15 * * * *", datetime(2026, 3, 4, 10, 0)) == datetime(2026, 3, 4, 10, 5)
assert next_run("5/15 * * * *", datetime(2026, 3, 4, 10, 5)) == datetime(2026, 3, 4, 10, 20)
assert next_run("10-20/5 * * * *", datetime(2026, 3, 4, 10, 0)) == datetime(2026, 3, 4, 10, 10)
assert next_run("0 0 * * */2", datetime(2026, 3, 2)) == datetime(2026, 3, 3, 0, 0)  # Sun, Tue, Thu, Sat
assert next_run("0 0 * * 5/1", datetime(2026, 3, 7, 0, 1)) == datetime(2026, 3, 8, 0, 0)  # 7 -> Sunday

# Day matching OR semantics.
assert next_run("0 0 1,15 * 5", datetime(2026, 1, 2, 0, 0)) == datetime(2026, 1, 9, 0, 0)
assert next_run("0 0 1,15 * 5", datetime(2026, 1, 15, 0, 0)) == datetime(2026, 1, 16, 0, 0)  # Friday
assert next_run("0 0 13 * 5", datetime(2026, 1, 1)) == datetime(2026, 1, 2, 0, 0)  # Friday only
assert next_run("0 0 */2 * *", datetime(2026, 3, 4)) == datetime(2026, 3, 5, 0, 0)  # restricted
assert next_run("0 0 * * *", datetime(2026, 3, 4, 12, 0)) == datetime(2026, 3, 5, 0, 0)
assert next_run("0 0 * * MON", datetime(2026, 3, 4)) == datetime(2026, 3, 9, 0, 0)

# Five years boundary: Feb 29 is reachable from just after Feb 29.
assert next_run("0 0 29 2 *", datetime(2028, 2, 29, 0, 0)) == datetime(2032, 2, 29, 0, 0)
assert next_run("0 0 29 2 *", datetime(2026, 3, 1, 12, 0)) == datetime(2028, 2, 29, 0, 0)

# A never-matching expression raises.
for expr in ("0 0 30 2 *", "0 0 31 4 *", "0 0 31 2,4,6,9,11 *"):
    try:
        next_run(expr, datetime(2026, 1, 1))
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for %r" % (expr,))


def expect_value_error(expr):
    try:
        next_run(expr, datetime(2026, 1, 1))
    except ValueError:
        return
    raise AssertionError("expected ValueError for %r" % (expr,))


# Wrong field counts.
for expr in ("", "   ", "* * * *", "* * * * * *", "@daily @daily",
             "@nope", "@weekly 1"):
    expect_value_error(expr)

# Out of range values.
for expr in ("60 * * * *", "-1 * * * *", "0 24 * * *", "0 0 0 * *",
             "0 0 32 * *", "0 0 * 0 *", "0 0 * 13 *", "0 0 * * 8"):
    expect_value_error(expr)

# Bad ranges / reversed ranges / names in the wrong field.
for expr in ("5-1 * * * *", "0 0 * DEC-JAN *", "0 0 * * FRI-MON",
             "1-2-3 * * * *", "JAN * * * *", "0 JAN * * *", "0 0 * * JAN",
             "0 0 MON * *", "* * * * MONDAY"):
    expect_value_error(expr)

# Bad steps.
for expr in ("*/0 * * * *", "*/ * * * *", "1//2 * * * *", "*/2/3 * * * *",
             "1-5/0 * * * *", "5/-1 * * * *", "*/+2 * * * *"):
    expect_value_error(expr)

# Empty items / stray separators.
for expr in ("1,,2 * * * *", "1, * * * *", ",1 * * * *", "1,2, * * * *",
             "* * * * *,", "* * ,, * *"):
    expect_value_error(expr)

# Non-str expr raises TypeError.
for bad in (None, 0, 1.5, ["* * * * *"], b"* * * * *"):
    try:
        next_run(bad, datetime(2026, 1, 1))
    except TypeError:
        pass
    else:
        raise AssertionError("expected TypeError for %r" % (bad,))

print("all tests passed")
