"""npm-style version range matching. See TASK.md for the exact spec."""

import re


_NUM = r"(?:0|[1-9][0-9]*)"
_IDENT = r"[0-9A-Za-z-]+"
_SEMVER = re.compile(
    r"^v?(?P<major>" + _NUM + r")\.(?P<minor>" + _NUM + r")\.(?P<patch>" + _NUM + r")"
    r"(?:-(?P<pre>" + _IDENT + r"(?:\." + _IDENT + r")*))?"
    r"(?:\+(?P<build>" + _IDENT + r"(?:\." + _IDENT + r")*))?$"
)


def _parse_version(value):
    if not isinstance(value, str):
        raise ValueError("version must be a string")
    value = value.strip()
    if value.startswith("="):
        value = value[1:]
    match = _SEMVER.fullmatch(value)
    if not match:
        raise ValueError("invalid version: %r" % value)
    pre = match.group("pre")
    if pre and any(x.isdigit() and len(x) > 1 and x[0] == "0" for x in pre.split(".")):
        raise ValueError("invalid numeric prerelease identifier")
    return (int(match.group("major")), int(match.group("minor")),
            int(match.group("patch")), tuple(pre.split(".")) if pre else None)


def _cmp(a, b):
    if a[:3] != b[:3]:
        return (a[:3] > b[:3]) - (a[:3] < b[:3])
    ap, bp = a[3], b[3]
    if ap is None or bp is None:
        return 0 if ap is bp else (1 if ap is None else -1)
    for x, y in zip(ap, bp):
        if x == y:
            continue
        xn, yn = x.isdigit(), y.isdigit()
        if xn and yn:
            return (int(x) > int(y)) - (int(x) < int(y))
        if xn != yn:
            return -1 if xn else 1
        return (x > y) - (x < y)
    return (len(ap) > len(bp)) - (len(ap) < len(bp))


def _bound(major, minor=0, patch=0, pre=None):
    return (major, minor, patch, tuple(pre.split(".")) if pre else None)


def _partial(text):
    """Return (version, number of specified numeric fields), or wildcard marker."""
    text = text.strip()
    if text.startswith("v") or text.startswith("="):
        text = text[1:]
    if text in ("*", "x", "X"):
        return None, 0
    # Prerelease/build are permitted only on complete versions.
    if "-" in text or "+" in text:
        return _parse_version(text), 3
    fields = text.split(".")
    if not 1 <= len(fields) <= 3:
        raise ValueError("invalid partial version: %r" % text)
    values = []
    wildcard = False
    for field in fields:
        if field in ("*", "x", "X"):
            wildcard = True
            values.append(None)
        elif not wildcard and re.fullmatch(_NUM, field):
            values.append(int(field))
        else:
            raise ValueError("invalid partial version: %r" % text)
    count = next((i for i, x in enumerate(values) if x is None), len(values))
    if count == 3:
        return _bound(values[0], values[1], values[2]), 3
    if count == 0:
        return None, 0
    padded = values[:count] + [0] * (3 - count)
    return _bound(*padded), count


def _inc(v, index):
    nums = list(v[:3])
    nums[index] += 1
    for i in range(index + 1, 3):
        nums[i] = 0
    return _bound(*nums, pre="0")


def _parse_comparator(token, operator=""):
    val, count = _partial(token)
    if count == 0:
        if operator in (">", "<"):
            return [(operator, None, False)]
        return []
    if count == 3:
        if operator in ("", "="):
            return [("=", val, bool(val[3]))]
        return [(operator, val, bool(val[3]))]
    if operator in ("", "="):
        return [(">=", val, False), ("<", _inc(val, count - 1), False)]
    if operator == ">=":
        return [(">=", val, False)]
    if operator == ">":
        return [(">=", _inc(val, count - 1), False)]
    if operator == "<":
        return [("<", val, False)]
    if operator == "<=":
        return [("<", _inc(val, count - 1), False)]
    raise ValueError("invalid comparator")


def _parse_set(source):
    source = source.strip()
    if not source:
        return []
    hyphen = re.fullmatch(r"(.+?)\s+-\s+(.+)", source)
    if hyphen:
        left, lc = _partial(hyphen.group(1))
        right, rc = _partial(hyphen.group(2))
        if left is None:
            lows = []
        else:
            lows = [(">=", left, bool(left[3]))]
        if right is None:
            highs = []
        elif rc == 3:
            highs = [("<=", right, bool(right[3]))]
        else:
            highs = [("<", _inc(right, rc - 1), False)]
        return lows + highs

    tokens = source.split()
    result = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        m = re.fullmatch(r"(<=|>=|<|>|=|~|\^)?(.*)", token)
        op, val = m.group(1) or "", m.group(2)
        if not val:
            i += 1
            if i >= len(tokens):
                raise ValueError("missing comparator version")
            val = tokens[i]
        if op in ("~", "^"):
            v, count = _partial(val)
            if v is None:
                if op == "~":
                    result.extend([])
                else:
                    result.extend([])
            else:
                result.append((">=", v, bool(v[3])))
                if op == "~":
                    idx = 0 if count == 1 else 1
                elif v[0] != 0:
                    idx = 0
                elif count == 1:
                    idx = 0
                elif v[1] != 0:
                    idx = 1
                elif count == 2:
                    idx = 1
                else:
                    idx = 2
                result.append(("<", _inc(v, idx), False))
        else:
            result.extend(_parse_comparator(val, op))
        i += 1
    return result


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("range must be a string")
    return [_parse_set(part) for part in range_.split("||")]


def _matches(version, comparator):
    op, bound, _explicit_pre = comparator
    if bound is None:
        return False
    c = _cmp(version, bound)
    return {"=": c == 0, ">": c > 0, ">=": c >= 0, "<": c < 0, "<=": c <= 0}[op]


def _satisfies_parsed(version, sets):
    for comparators in sets:
        if not all(_matches(version, c) for c in comparators):
            continue
        if version[3] is not None and not any(
            c[2] and c[1] is not None and c[1][:3] == version[:3]
            for c in comparators
        ):
            continue
        return True
    return False


def satisfies(version, range_):
    parsed = _parse_version(version)
    ranges = _parse_range(range_)
    return _satisfies_parsed(parsed, ranges)


def max_satisfying(versions, range_):
    ranges = _parse_range(range_)
    best_text, best = None, None
    for item in versions:
        try:
            parsed = _parse_version(item)
        except (ValueError, AttributeError):
            continue
        if _satisfies_parsed(parsed, ranges) and (best is None or _cmp(parsed, best) > 0):
            best_text, best = item, parsed
    return best_text
