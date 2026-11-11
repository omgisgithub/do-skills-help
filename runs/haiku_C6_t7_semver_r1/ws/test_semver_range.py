"""Checks for semver_range.py, written from the examples and rules in TASK.md."""

from semver_range import _parse_version, max_satisfying, satisfies


def yes(version, range_):
    assert satisfies(version, range_) is True, (version, range_)


def no(version, range_):
    assert satisfies(version, range_) is False, (version, range_)


def invalid_version(version):
    try:
        satisfies(version, "*")
    except ValueError:
        return
    raise AssertionError("version should be invalid: %r" % (version,))


def invalid_range(range_):
    try:
        satisfies("1.2.3", range_)
    except ValueError:
        return
    raise AssertionError("range should be invalid: %r" % (range_,))


def test_ordering_chain():
    chain = [
        "1.0.0-alpha",
        "1.0.0-alpha.1",
        "1.0.0-alpha.beta",
        "1.0.0-beta",
        "1.0.0-beta.2",
        "1.0.0-beta.11",
        "1.0.0-rc.1",
        "1.0.0",
    ]
    keys = [_parse_version(v)[2] for v in chain]
    assert keys == sorted(keys) and len(set(keys)) == len(keys)
    yes("1.0.0-beta.11", "<1.0.0-rc.1")
    yes("1.0.0-rc.1", ">1.0.0-beta.11")
    no("1.0.0-beta.2", ">1.0.0-beta.11")
    yes("1.0.0+build.5", "1.0.0")
    yes("1.0.0-alpha+a", "=1.0.0-alpha+b")


def test_caret():
    for r, ys, ns in [
        ("^1.2.3", ["1.2.3", "1.9.9", "1.2.4"], ["2.0.0", "1.2.2", "2.0.0-0", "1.2.4-alpha"]),
        ("^0.2.3", ["0.2.3", "0.2.9"], ["0.3.0", "0.2.2", "0.3.0-0"]),
        ("^0.0.3", ["0.0.3"], ["0.0.4", "0.0.4-0", "0.0.2"]),
        ("^1.2.3-beta.2", ["1.2.3-beta.2", "1.2.3-beta.4", "1.2.3", "1.9.0"],
         ["1.2.3-beta.1", "1.2.4-alpha", "2.0.0"]),
        ("^1.2", ["1.2.0", "1.9.9"], ["1.1.9", "2.0.0"]),
        ("^1.2.x", ["1.2.0", "1.9.9"], ["1.1.9", "2.0.0"]),
        ("^1", ["1.0.0", "1.9.0"], ["0.9.9", "2.0.0"]),
        ("^1.x", ["1.0.0", "1.9.0"], ["0.9.9", "2.0.0"]),
        ("^0.0", ["0.0.0", "0.0.99"], ["0.1.0", "0.1.0-0"]),
        ("^0.0.x", ["0.0.0", "0.0.99"], ["0.1.0", "0.1.0-0"]),
        ("^0.x", ["0.0.0", "0.9.9"], ["1.0.0", "1.0.0-0"]),
        ("^0", ["0.0.0", "0.9.9"], ["1.0.0", "1.0.0-0"]),
        ("^0.1", ["0.1.0", "0.1.9"], ["0.2.0"]),
    ]:
        for v in ys:
            yes(v, r)
        for v in ns:
            no(v, r)


def test_tilde():
    for r, ys, ns in [
        ("~1.2.3", ["1.2.3", "1.2.9"], ["1.3.0", "1.2.2"]),
        ("~1.2", ["1.2.0", "1.2.9"], ["1.3.0"]),
        ("~1", ["1.0.0", "1.9.9"], ["2.0.0"]),
        ("~0.2.3", ["0.2.3", "0.2.9"], ["0.3.0"]),
        ("~1.2.3-beta.2", ["1.2.3-beta.2", "1.2.3", "1.2.9"],
         ["1.3.0-0", "1.2.3-beta.1", "1.2.4-alpha"]),
    ]:
        for v in ys:
            yes(v, r)
        for v in ns:
            no(v, r)


def test_comparators_and_partials():
    yes("1.3.0", ">1.2")
    no("1.2.9", ">1.2")
    no("1.3.0-rc.1", ">1.2")
    yes("2.0.0", ">1")
    no("1.9.9", ">1")
    yes("1.2.0", ">=1.2")
    no("1.1.9", ">=1.2")
    yes("1.1.9", "<1.2")
    no("1.2.0", "<1.2")
    no("1.2.0-0", "<1.2")
    no("1.1.9-alpha", "<1.2")
    yes("1.2.9", "<=1.2")
    no("1.3.0", "<=1.2")
    yes("1.9.9", "<=1")
    no("2.0.0", "<=1")
    yes("1.2.0", "=1.2")
    yes("1.2.9", "=1.2")
    no("1.3.0", "=1.2")
    no("1.1.9", "=1.2")
    yes("1.2.3", "1.2.3")
    yes("1.2.3", "=1.2.3")
    yes("1.2.3", "= 1.2.3")
    yes("1.2.3", "v1.2.3")
    yes("1.2.3", ">= 1.2.3")
    yes("1.2.3", ">=1.0.0 <2.0.0")
    no("2.0.0", ">=1.0.0 <2.0.0")
    no("1.2.3", ">1.2.3")


def test_wildcards():
    for w in ["*", "x", "X", ">=*", "<=*", ">=0.0.0", ""]:
        yes("0.0.0", w)
        yes("1.2.3", w)
        yes("99.0.0", w)
        no("1.0.0-rc.1", w)
    for w in [">*", "<*"]:
        no("0.0.0", w)
        no("1.0.0", w)
    for w in ["1.2.x", "1.2.*", "1.2", "=1.2.X"]:
        yes("1.2.0", w)
        yes("1.2.9", w)
        no("1.3.0", w)
        no("1.1.9", w)
    for w in ["1.x", "1.x.x", "1", "1.*", "1.X.X"]:
        yes("1.0.0", w)
        yes("1.9.9", w)
        no("2.0.0", w)
        no("0.9.9", w)


def test_hyphen():
    yes("1.2.3", "1.2.3 - 2.3.4")
    yes("2.3.4", "1.2.3 - 2.3.4")
    yes("2.3.0", "1.2.3 - 2.3.4")
    no("1.2.2", "1.2.3 - 2.3.4")
    no("2.3.5", "1.2.3 - 2.3.4")
    yes("1.2.0", "1.2 - 2.3.4")
    yes("2.3.4", "1.2 - 2.3.4")
    no("1.1.9", "1.2 - 2.3.4")
    no("2.3.5", "1.2 - 2.3.4")
    yes("2.3.9", "1.2.3 - 2.3")
    no("2.4.0", "1.2.3 - 2.3")
    no("2.4.0-0", "1.2.3 - 2.3")
    yes("2.9.9", "1.2.3 - 2")
    no("3.0.0", "1.2.3 - 2")
    no("3.0.0-0", "1.2.3 - 2")


def test_prerelease_rule():
    no("1.2.4-alpha", "^1.2.3")
    yes("1.2.3-beta.4", "^1.2.3-beta.2")
    no("1.0.0-rc.1", "*")
    yes("1.0.0-rc.1", ">=1.0.0-beta.11 <1.0.0")
    no("1.0.0-rc.1", ">=0.9.0 <1.0.0")


def test_or_sets():
    yes("1.2.5", "1.2.x || >=2.5.0 <3.0.0")
    yes("2.5.1", "1.2.x || >=2.5.0 <3.0.0")
    no("2.4.0", "1.2.x || >=2.5.0 <3.0.0")
    no("3.0.0", "1.2.x || >=2.5.0 <3.0.0")
    yes("1.0.0", "1.0.0 ||")
    yes("2.0.0", "1.0.0 ||")
    no("2.0.0-rc.1", "1.0.0 ||")


def test_must_fail_versions():
    for v in [
        "01.2.3", "1.02.3", "1.2", "1.2.3.4", "1.2.3-01", "1.2.3-", "1.2.3-a..b",
        "1.2.3+", "v=1.2.3", "=v1.2.3", "==1.2.3", "1.2.3 4", "vv1.2.3", "V1.2.3",
        "1. 2.3", "1.2.x", "1.2.3-beta_1", "", "v", "a.b.c", "-1.2.3", "1.2.3-beta..1",
    ]:
        invalid_version(v)


def test_must_pass_versions():
    yes("1.2.3+01", "1.2.3")
    yes("  v1.2.3  ", "1.2.3")
    yes("=1.2.3", "1.2.3")
    yes("0.0.0", "0.0.0")


def test_must_fail_ranges():
    for r in [
        "~>1.2", ">=1.2.3 -", "1.2.3 -", "- 1.2.3", "1.2.3 -2.3.4", "1.2.3 - 2.3.4 - 5",
        "^", "~", ">=", "<", ">=a.b.c", "1.2.3.4", ">==1.2.3", "< =1.2.3", "> >=1.2.3",
        "1.x.3", "x.1", "*.1", "1.*.3", "1.2-beta", ">1.2.3-", "v", "vv1.2.3",
        "1.2.3-01", ">=1.2.3 - 2.3.4", "1.2.3 - 2.3.4 - ", "^1.2.3-01",
    ]:
        invalid_range(r)


def test_max_satisfying():
    assert max_satisfying(["1.2.3", "1.2.4", "1.3.0", "2.0.0"], "^1.2.3") == "1.3.0"
    assert max_satisfying(["1.2.3", "1.2.4", "1.3.0", "2.0.0"], "~1.2.3") == "1.2.4"
    assert max_satisfying(["v1.2.4", "1.2.4+b"], "*") == "v1.2.4"
    assert max_satisfying(["1.2.4+b", "v1.2.4"], "*") == "1.2.4+b"
    assert max_satisfying(["1.0.0", "x"], "*") == "1.0.0"
    assert max_satisfying(["1.0.0", "bad", 5, "1.1.0"], "*") == "1.1.0"
    assert max_satisfying(["1.0.0"], "^2") is None
    assert max_satisfying([], "*") is None
    assert max_satisfying(["1.0.0-rc.1", "0.9.0"], "*") == "0.9.0"
    assert max_satisfying(["1.2.3-beta.4", "1.2.3"], "^1.2.3-beta.2") == "1.2.3"
    assert max_satisfying(["1.2.3-beta.4", "1.2.4-alpha"], "^1.2.3-beta.2") == "1.2.3-beta.4"
    for bad_range in ["~>1", "1.2.3.4"]:
        try:
            max_satisfying([], bad_range)
        except ValueError:
            continue
        raise AssertionError("invalid range should raise: %r" % (bad_range,))


def test_satisfies_raises_on_invalid_version():
    for v in ["1.2", "01.2.3", "v=1.2.3"]:
        try:
            satisfies(v, "*")
        except ValueError:
            continue
        raise AssertionError("should raise for %r" % (v,))


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("all passed")
