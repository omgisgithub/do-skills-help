"""npm-style version range matching. See TASK.md for the exact spec."""

import re


_VERSION = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?\Z"
)
_PARTIAL = re.compile(r"(0|[1-9][0-9]*|[xX*])(?:\.(0|[1-9][0-9]*|[xX*])){0,2}\Z")


def _parse_version(value):
    value = value.strip()
    if value.startswith(("v", "=")):
        value = value[1:]
    match = _VERSION.fullmatch(value)
    if not match:
        raise ValueError("invalid version")
    major, minor, patch, pre, build = match.groups()
    if pre and any(x.isdigit() and len(x) > 1 and x[0] == "0" for x in pre.split(".")):
        raise ValueError("invalid numeric prerelease identifier")
    return (int(major), int(minor), int(patch), tuple(pre.split(".")) if pre else ())


def _cmp(a, b):
    if a[:3] != b[:3]:
        return (a[:3] > b[:3]) - (a[:3] < b[:3])
    ap, bp = a[3], b[3]
    if not ap or not bp:
        return 0 if not ap and not bp else (1 if not ap else -1)
    for x, y in zip(ap, bp):
        xn, yn = x.isdigit(), y.isdigit()
        if xn and yn:
            n = (int(x) > int(y)) - (int(x) < int(y))
        elif xn != yn:
            n = -1 if xn else 1
        else:
            n = (x > y) - (x < y)
        if n:
            return n
    return (len(ap) > len(bp)) - (len(ap) < len(bp))


def _partial(text):
    match = _PARTIAL.fullmatch(text)
    if not match:
        raise ValueError("invalid partial version")
    fields = text.split(".")
    vals = []
    wildcard = False
    for field in fields:
        if field in ("*", "x", "X"):
            wildcard = True
            vals.append(None)
        else:
            if wildcard:
                raise ValueError("numeric component after wildcard")
            vals.append(int(field))
    return vals


def _bound(v):
    return (v[0], v[1], v[2], ())


def _upper(vals):
    known = len(vals)
    nums = [x for x in vals if x is not None]
    if known == 1:
        return (nums[0] + 1, 0, 0, ("0",))
    if known == 2:
        return (nums[0], nums[1] + 1, 0, ("0",))
    return (nums[0], nums[1], nums[2] + 1, ("0",))


def _partial_upper(vals):
    return _upper(vals[:vals.index(None)] if None in vals else vals)


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("range must be a string")
    sets = []
    for raw in range_.split("||"):
        raw = raw.strip()
        comps = []
        # Hyphen ranges are recognized only with whitespace on both sides.
        hm = re.fullmatch(r"\s*(\S+)\s+-\s+(\S+)\s*", raw)
        if hm:
            left, right = hm.groups()
            lv = _partial(left)
            if any(x is None for x in lv):
                raise ValueError("invalid hyphen lower bound")
            while len(lv) < 3:
                lv.append(0)
            comps.append((">=", _bound(lv), False))
            rv = _partial(right)
            if any(x is None for x in rv):
                first = next(i for i, x in enumerate(rv) if x is None)
                if any(x is not None for x in rv[first:]):
                    raise ValueError("invalid partial")
                comps.append(("<", _upper(rv[:first]), False))
            elif len(rv) < 3:
                comps.append(("<", _upper(rv), False))
            else:
                comps.append(("<=", _bound(rv), False))
            sets.append(comps)
            continue
        # Join operators to their following token, allowing operator whitespace.
        tokens = raw.split()
        normalized = []
        i = 0
        while i < len(tokens):
            if tokens[i] in ("<", "<=", ">", ">=", "=", "~", "^"):
                if i + 1 == len(tokens):
                    raise ValueError("missing comparator version")
                normalized.append(tokens[i] + tokens[i + 1]); i += 2
            else:
                normalized.append(tokens[i]); i += 1
        for token in normalized:
            m = re.fullmatch(r"(<=|>=|<|>|=|~|\^)?(.*)", token)
            op, body = m.groups()
            if not body:
                raise ValueError("missing version")
            op = op or "="
            if body in ("*", "x", "X"):
                if op in (">", "<"):
                    # An impossible comparator is represented explicitly.
                    comps.append(("!", None, False))
                elif op in (">=", "<=", "="):
                    continue
                else:
                    raise ValueError("invalid wildcard operator")
                continue
            # Full versions may carry prerelease/build; partials may not.
            full_text = body[1:] if body.startswith(("v", "=")) else body
            full = _VERSION.fullmatch(full_text)
            if full:
                v = _parse_version(body)
                if op in ("~", "^"):
                    comps.append((">=", v, bool(v[3])))
                    major, minor, patch = v[:3]
                    if op == "~":
                        upper = (major + 1, 0, 0, ("0",)) if len(body.split(".")[0]) and body.count(".") == 0 else (major, minor + 1, 0, ("0",))
                    elif major:
                        upper = (major + 1, 0, 0, ("0",))
                    elif minor:
                        upper = (0, minor + 1, 0, ("0",))
                    else:
                        upper = (0, 0, patch + 1, ("0",))
                    comps.append(("<", upper, False))
                else:
                    comps.append((op, v, bool(v[3])))
                continue
            vals = _partial(body)
            if op in ("~", "^"):
                base = vals[:]
                while len(base) < 3: base.append(0)
                comps.append((">=", _bound(base), False))
                if op == "~":
                    upper = (base[0] + 1, 0, 0, ("0",)) if len(vals) == 1 else (base[0], base[1] + 1, 0, ("0",))
                elif vals[0] != 0 or vals[0] is None:
                    upper = (base[0] + 1, 0, 0, ("0",))
                elif len(vals) == 1 or vals[1] is None:
                    upper = (1, 0, 0, ("0",))
                elif vals[1] != 0:
                    upper = (0, base[1] + 1, 0, ("0",))
                elif len(vals) < 3 or vals[2] is None:
                    upper = (0, 1, 0, ("0",))
                else:
                    upper = (0, 0, base[2] + 1, ("0",))
                comps.append(("<", upper, False))
            elif op in ("=", ">="):
                base = vals[:]
                if any(x is None for x in vals):
                    first = vals.index(None)
                    base = vals[:first]
                while len(base) < 3: base.append(0)
                comps.append((">=", _bound(base), False))
                if len(vals) < 3 or any(x is None for x in vals):
                    comps.append(("<", _partial_upper(vals), False))
                elif op == "=":
                    comps.append(("<=", _bound(base), False))
                else:
                    comps.pop(0); comps.append((">=", _bound(base), False))
            elif op in (">", "<", "<="):
                if len(vals) == 3 and not any(x is None for x in vals):
                    comps.append((op, _bound(vals), False))
                elif op == ">":
                    comps.append((">=", _partial_upper(vals), False))
                elif op == "<":
                    base = vals[:]
                    while len(base) < 3: base.append(0)
                    comps.append(("<", _bound(base), False))
                else:
                    comps.append(("<", _partial_upper(vals), False))
        sets.append(comps)
    return sets


def _matches(version, comps):
    for op, bound, _ in comps:
        if op == "!": return False
        c = _cmp(version, bound)
        if not ({"<": c < 0, "<=": c <= 0, ">": c > 0, ">=": c >= 0, "=": c == 0}[op]):
            return False
    if version[3] and not any(pre and version[:3] == bound[:3] for _, bound, pre in comps if bound):
        return False
    return True


def satisfies(version: str, range_: str) -> bool:
    parsed = _parse_version(version)
    return any(_matches(parsed, comps) for comps in _parse_range(range_))


def max_satisfying(versions: list, range_: str):
    sets = _parse_range(range_)
    best = None
    best_parsed = None
    for value in versions:
        try:
            parsed = _parse_version(value)
        except (ValueError, AttributeError):
            continue
        if any(_matches(parsed, comps) for comps in sets):
            if best is None or _cmp(parsed, best_parsed) > 0:
                best, best_parsed = value, parsed
    return best
