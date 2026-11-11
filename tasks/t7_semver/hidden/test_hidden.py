from semver_range import satisfies, max_satisfying

YES = [
    ("1.2.3", "1.2.3"), ("v1.2.3", "=1.2.3"), (" =1.2.3 ", "1.2.3"), ("1.2.3+build.5", "1.2.3"),
    ("1.2.3", ">=1.2.3"), ("1.2.4", ">1.2.3"), ("1.2.2", "<1.2.3"), ("1.2.3", "<=1.2.3"),
    ("1.2.3", ">= 1.2.3"), ("1.5.0", ">=1.2.3 <2.0.0"), ("3.0.0", "<1 || >=3"),
    ("1.2.9", "1.2"), ("1.2.0", "1.2.x"), ("1.2.7", "1.2.*"), ("1.9.9", "1"), ("1.0.0", "1.x.x"),
    ("0.0.0", "*"), ("9.9.9", "x"), ("4.5.6", ""), ("4.5.6", "  "), ("2.0.0", ">=*"),
    ("1.3.0", ">1.2"), ("2.0.0", ">1"), ("1.2.0", ">=1.2"), ("1.1.9", "<1.2"),
    ("1.2.99", "<=1.2"), ("1.99.0", "<=1"),
    ("1.2.3", "~1.2.3"), ("1.2.9", "~1.2.3"), ("1.2.0", "~1.2"), ("1.9.0", "~1"),
    ("0.2.5", "~0.2.3"), ("1.2.3-beta.4", "~1.2.3-beta.2"), ("1.2.5", "~1.2.3-beta.2"),
    ("1.9.9", "^1.2.3"), ("0.2.9", "^0.2.3"), ("0.0.3", "^0.0.3"), ("1.2.3-beta.4", "^1.2.3-beta.2"),
    ("1.8.0", "^1.2.3-beta.2"), ("1.5.0", "^1.2"), ("1.2.0", "^1.2.x"), ("1.0.0", "^1"),
    ("0.0.9", "^0.0"), ("0.0.1", "^0.0.x"), ("0.9.9", "^0.x"), ("0.5.0", "^0"), ("0.1.5", "^0.1"),
    ("1.2.3", "1.2.3 - 2.3.4"), ("2.3.4", "1.2.3 - 2.3.4"), ("1.2.0", "1.2 - 2.3.4"),
    ("2.3.9", "1.2.3 - 2.3"), ("2.9.9", "1.2.3 - 2"),
    ("1.0.0-alpha.1", ">=1.0.0-alpha"), ("1.0.0-beta.11", ">1.0.0-beta.2"),
    ("1.0.0-rc.1", ">=1.0.0-alpha.beta <1.0.0"), ("1.0.0", ">1.0.0-rc.1"),
    ("1.2.3-alpha.7", ">=1.2.3-alpha.3 || >=2.0.0"), ("1.2.3-0", "1.2.3-0"),
    ("1.0.0-x-y-z.1", "1.0.0-x-y-z.1"), ("1.0.0-alpha+001", "=1.0.0-alpha"),
    ("2.1.0", "~1.2.3 || ^2.0.0"), ("1.2.3", ">=1.2.3 <=1.2.3"),
]
NO = [
    ("1.2.4", "1.2.3"), ("1.2.3", ">1.2.3"), ("1.2.3", "<1.2.3"), ("2.0.0", ">=1.2.3 <2.0.0"),
    ("1.3.0", "1.2"), ("2.0.0", "1"), ("1.2.9", ">1.2"), ("1.2.0", "<1.2"), ("1.3.0", "<=1.2"),
    ("2.0.0", "<=1"), ("1.1.9", ">=1.2"), ("3.0.0", ">*"), ("0.0.0", "<*"),
    ("1.3.0", "~1.2.3"), ("1.2.2", "~1.2.3"), ("2.0.0", "~1"), ("0.3.0", "~0.2.3"),
    ("1.3.0-beta.4", "~1.2.3-beta.2"), ("1.2.3-beta.1", "~1.2.3-beta.2"),
    ("2.0.0", "^1.2.3"), ("1.2.2", "^1.2.3"), ("0.3.0", "^0.2.3"), ("0.0.4", "^0.0.3"),
    ("0.1.0", "^0.0"), ("0.1.0", "^0.0.x"), ("1.0.0", "^0.x"), ("0.2.0", "^0.1"),
    ("2.0.0-alpha", "^1.2.3"), ("1.1.0", "^1.2"),
    ("2.3.5", "1.2.3 - 2.3.4"), ("1.2.2", "1.2.3 - 2.3.4"), ("2.4.0", "1.2.3 - 2.3"), ("3.0.0", "1.2.3 - 2"),
    # prerelease rule
    ("1.2.4-alpha", "^1.2.3"), ("1.2.4-alpha", "~1.2.3"), ("1.2.4-alpha", ">=1.2.3"),
    ("1.0.0-rc.1", "*"), ("1.0.0-rc.1", ""), ("1.0.0-rc.1", "1.x"), ("1.2.3-beta", "1.2"),
    ("2.0.0-rc.1", "^1.0.0 || ^2.0.0"), ("1.2.5-beta.1", "^1.2.3-beta.2"),
    ("1.2.3-beta", ">=1.2.0 <1.3.0"), ("1.0.0-beta.2", ">1.0.0-beta.11"),
    ("1.0.0-alpha", ">=1.0.0-alpha.1"), ("1.0.0-beta", "1.0.0-beta.0"),
    ("1.0.0", "<1.0.0-rc.1"),
]
BAD_VERSIONS = ["1.2", "1.2.3.4", "01.2.3", "1.02.3", "1.2.3-", "1.2.3-01", "1.2.3+", "a.b.c",
                "", "  ", "1.2.3-be$ta", "vv1.2.3", "1.2.3-alpha..1", "-1.2.3"]
BAD_RANGES = ["~>1.2", ">=1.2.3 -", "1.2.3.4", "^", ">=", ">=a.b.c", "1.2.3 - ", "- 1.2.3",
              "1.x.3", "^1.2.3.4", "1.2.3-01", "1.x-beta"]


def test_yes():
    bad = [(v, r) for v, r in YES if satisfies(v, r) is not True]
    assert not bad, bad


def test_no():
    bad = [(v, r) for v, r in NO if satisfies(v, r) is not False]
    assert not bad, bad


def test_bad_versions():
    ok = []
    for v in BAD_VERSIONS:
        try:
            satisfies(v, "*")
            ok.append(v)
        except ValueError:
            pass
    assert not ok, ok


def test_bad_ranges():
    ok = []
    for r in BAD_RANGES:
        try:
            satisfies("1.2.3", r)
            ok.append(r)
        except ValueError:
            pass
    assert not ok, ok


def test_prerelease_ordering():
    chain = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2",
             "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0"]
    for a, b in zip(chain, chain[1:]):
        assert satisfies(b, ">" + a) or b == "1.0.0", (a, b)
        if "-" in b:  # a prerelease only matches comparators written with its own tuple + tag
            assert satisfies(a, "<" + b), (a, b)
        assert not satisfies(b, "<" + a), (a, b)
    assert not satisfies("1.0.0-rc.1", "<1.0.0")


def test_max_satisfying():
    vs = ["1.2.3", "1.2.4", "1.3.0", "2.0.0-rc.1", "2.0.0", "garbage", "1.2.10"]
    assert max_satisfying(vs, "~1.2.0") == "1.2.10"
    assert max_satisfying(vs, "^1.0.0") == "1.3.0"
    assert max_satisfying(vs, ">=2.0.0-rc.1") == "2.0.0"
    assert max_satisfying(vs, "<2.0.0-rc.5 >=2.0.0-rc.0") == "2.0.0-rc.1"
    assert max_satisfying(vs, "^3") is None
    assert max_satisfying(["1.0.0+a", "1.0.0+b", "v1.0.0"], "1") == "1.0.0+a"
    assert max_satisfying(["1.0.0-rc.1", "0.9.0"], "*") == "0.9.0"
    assert max_satisfying([], "*") is None
    try:
        max_satisfying(vs, "~>1")
        raise AssertionError("invalid range accepted")
    except ValueError:
        pass


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
