import sys
from duration import parse_duration as P

GOOD = {
    "1h30m": 5400, " 2d 4h ": 187200, "1.5h": 5400, "1w2d3h4m5s": 788645, "1:02:03": 3723,
    "-45s": -45, "0": 0, "-0s": 0, "0s": 0, "05m": 300, "1.5m": 90, "0.1h": 360, "0.25m": 15,
    "1h 30m": 5400, "1w 1s": 604801, "1:30": 90, "1:00:00": 3600, "90:00": 5400, "-1:30": -90,
    "0:00": 0, "100:59:59": 363599, "-1h": -3600, "2.5d": 216000,
    "\t3m\n": 180, "1d1s": 86401, "1.000s": 1,
    "1.25w": 756000, "10s": 10, "0:59": 59, "00:00:01": 1,
}

BAD = [
    "", "   ", "5", "1.5", "+5s", "1 h", "30m1h", "1h1h", ".5h", "5.h", "1H", "0.3s", "1:60",
    "1:5", "1:30.5", "1h  30m", "1h,30m", "--1h", "- 1h", "1h-", "h", "1x", "1:00:60", ":30",
    "1::30", "1:30:", "1h30", "1d 1d", "1m1h", "1.5:30", "1:2:3", "1h 1:30", "1s 1m", "1e3s",
    "0.5s", "1.0001s", "abc", "0.0001w", "0.001w", "1:0:00", "12:345", "0x10s",
] 
GOOD["1h 30m "] = 5400  # trailing space is stripped


def test_good():
    bad = []
    for s, v in GOOD.items():
        try:
            got = P(s)
        except Exception as e:
            got = type(e).__name__
        if got != v or type(got) is not int:
            bad.append((s, v, got))
    assert not bad, bad


def test_bad():
    wrong = []
    for s in BAD:
        try:
            got = P(s)
            wrong.append((s, got))
        except ValueError:
            pass
        except Exception as e:
            wrong.append((s, type(e).__name__))
    assert not wrong, wrong


def test_type_error():
    for x in [None, 5, 1.5, b"1h", ["1h"]]:
        try:
            P(x)
        except TypeError:
            continue
        except Exception as e:
            raise AssertionError("%r raised %s" % (x, type(e).__name__))
        raise AssertionError("%r accepted" % (x,))


def test_big_exact():
    assert P("123456789012345678w") == 123456789012345678 * 604800


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as e:
                fails += 1
                print("FAIL", name, type(e).__name__, str(e)[:800])
    sys.exit(1 if fails else 0)
