import time
from datetime import datetime
from cronexpr import next_run

CASES = [
    ('*/15 * * * *', datetime(2026, 3, 4, 10, 7), datetime(2026, 3, 4, 10, 15)),
    ('0 9 * * MON-FRI', datetime(2026, 3, 6, 9, 0), datetime(2026, 3, 9, 9, 0)),
    ('0 0 29 2 *', datetime(2026, 3, 1, 0, 0), datetime(2028, 2, 29, 0, 0)),
    ('30 4 1,15 * 5', datetime(2026, 1, 1, 5, 0), datetime(2026, 1, 2, 4, 30)),
    ('* * * * *', datetime(2026, 5, 5, 12, 0, 30), datetime(2026, 5, 5, 12, 1)),
    ('* * * * *', datetime(2026, 5, 5, 12, 0), datetime(2026, 5, 5, 12, 1)),
    ('* * * * *', datetime(2026, 12, 31, 23, 59, 59, 999999), datetime(2027, 1, 1, 0, 0)),
    ('0 0 1 1 *', datetime(2026, 1, 1, 0, 0), datetime(2027, 1, 1, 0, 0)),
    ('@yearly', datetime(2026, 6, 1, 0, 0), datetime(2027, 1, 1, 0, 0)),
    ('@ANNUALLY', datetime(2026, 6, 1, 0, 0), datetime(2027, 1, 1, 0, 0)),
    ('@monthly', datetime(2026, 1, 31, 0, 1), datetime(2026, 2, 1, 0, 0)),
    ('@weekly', datetime(2026, 10, 31, 12, 0), datetime(2026, 11, 1, 0, 0)),
    ('@daily', datetime(2026, 2, 28, 23, 59), datetime(2026, 3, 1, 0, 0)),
    ('@midnight', datetime(2028, 2, 28, 0, 0), datetime(2028, 2, 29, 0, 0)),
    ('@hourly', datetime(2026, 3, 1, 23, 0), datetime(2026, 3, 2, 0, 0)),
    ('5/15 * * * *', datetime(2026, 3, 1, 10, 51), datetime(2026, 3, 1, 11, 5)),
    ('1-10/3 * * * *', datetime(2026, 3, 1, 10, 8), datetime(2026, 3, 1, 10, 10)),
    ('0 0 * * 7', datetime(2026, 10, 28, 0, 0), datetime(2026, 11, 1, 0, 0)),
    ('0 0 * * 0', datetime(2026, 10, 28, 0, 0), datetime(2026, 11, 1, 0, 0)),
    ('0 0 * * 5-7', datetime(2026, 11, 2, 0, 0), datetime(2026, 11, 6, 0, 0)),
    ('0 0 * * sun', datetime(2026, 11, 2, 0, 0), datetime(2026, 11, 8, 0, 0)),
    ('0 12 * jan,Jul mon', datetime(2026, 2, 1, 0, 0), datetime(2026, 7, 6, 12, 0)),
    ('0 0 13 * FRI', datetime(2026, 3, 1, 0, 0), datetime(2026, 3, 6, 0, 0)),
    ('0 0 31 2 1', datetime(2026, 3, 3, 0, 0), datetime(2027, 2, 1, 0, 0)),
    ('0 0 */2 * *', datetime(2026, 1, 31, 0, 0), datetime(2026, 2, 1, 0, 0)),
    ('0 0 */2 * MON', datetime(2026, 1, 1, 0, 0), datetime(2026, 1, 3, 0, 0)),
    ('0 0 * * */3', datetime(2026, 10, 31, 0, 0), datetime(2026, 11, 1, 0, 0)),
    ('59 23 31 12 *', datetime(2026, 12, 31, 23, 59), datetime(2027, 12, 31, 23, 59)),
    ('0 0 31 * *', datetime(2026, 4, 1, 0, 0), datetime(2026, 5, 31, 0, 0)),
    ('15 10 * * 1-5', datetime(2026, 10, 30, 10, 15), datetime(2026, 11, 2, 10, 15)),
    ('0 22 * * 1-5', datetime(2026, 10, 30, 22, 0, 1), datetime(2026, 11, 2, 22, 0)),
    ('  0\t9  *   *  1 ', datetime(2026, 10, 31, 0, 0), datetime(2026, 11, 2, 9, 0)),
    ('0 0 1 */3 *', datetime(2026, 2, 1, 0, 0), datetime(2026, 4, 1, 0, 0)),
    ('0 0 1 FEB-APR/2 *', datetime(2026, 5, 1, 0, 0), datetime(2027, 2, 1, 0, 0)),
    ('0 0 28-31 * *', datetime(2026, 2, 1, 0, 0), datetime(2026, 2, 28, 0, 0)),
    ('45 23 * * 6', datetime(2026, 12, 26, 23, 45), datetime(2027, 1, 2, 23, 45)),
    ('0 0 29 2 1', datetime(2026, 3, 1, 0, 0), datetime(2027, 2, 1, 0, 0)),
    ('0,30 8-9 * * *', datetime(2026, 3, 1, 9, 30), datetime(2026, 3, 2, 8, 0)),
]
NEVER = ["0 0 30 2 *", "0 0 31 4,6,9,11 *", "0 0 31 2 *"]
INVALID = ["", "* * * *", "* * * * * *", "60 * * * *", "* 24 * * *", "* * 0 * *", "* * 32 * *",
           "* * * 13 *", "* * * 0 *", "* * * * 8", "*/0 * * * *", "5-1 * * * *", "* * * * FRI-MON",
           "* * * * JAN", "* * * MON *", "1,,2 * * * *", "1, * * * *", "a * * * *", "-1 * * * *",
           "* * * * * extra", "@every_5m", "@reboot", "1-2-3 * * * *", "*/ * * * *", "1/2/3 * * * *",
           "** * * * *", "*-5 * * * *", "0 0 L * *", "0 0 15W * *", "0 0 * * 5#3", "0 0 ? * *"]


def test_cases():
    bad = []
    for e, a, want in CASES:
        try:
            got = next_run(e, a)
        except Exception as ex:
            got = repr(ex)
        if got != want:
            bad.append((e, str(a), str(got), str(want)))
    assert not bad, bad


def test_seconds_zeroed():
    r = next_run("* * * * *", datetime(2026, 5, 5, 12, 0, 30, 5))
    assert r.second == 0 and r.microsecond == 0, r


def test_never():
    ok = []
    for e in NEVER:
        try:
            next_run(e, datetime(2026, 1, 1))
            ok.append(e)
        except ValueError:
            pass
    assert not ok, ok


def test_invalid():
    ok = []
    for e in INVALID:
        try:
            next_run(e, datetime(2026, 1, 1))
            ok.append(e)
        except ValueError:
            pass
    assert not ok, ok


def test_type_error():
    for e in (None, 5, b"* * * * *"):
        try:
            next_run(e, datetime(2026, 1, 1))
            raise AssertionError("accepted %r" % (e,))
        except TypeError:
            pass


def test_speed():
    t = time.time()
    for _ in range(20):
        next_run("0 0 29 2 1", datetime(2026, 3, 1))
        next_run("59 23 31 12 *", datetime(2026, 12, 31, 23, 59))
    assert time.time() - t < 20, "too slow"


if __name__ == "__main__":
    import sys
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as e:
                fails += 1
                print("FAIL", name, type(e).__name__, str(e)[:600])
    sys.exit(1 if fails else 0)
