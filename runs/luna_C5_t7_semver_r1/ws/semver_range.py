"""npm-style version range matching. See TASK.md for the exact spec."""

import re

_VERSION_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$")
_PART_RE = re.compile(r"^(0|[1-9][0-9]*|[xX*])(?:\.(0|[1-9][0-9]*|[xX*]))?(?:\.(0|[1-9][0-9]*|[xX*]))?(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$")


def _parse_version(value):
    if not isinstance(value, str):
        raise ValueError("version must be a string")
    value = value.strip()
    if value.startswith(("v", "=")):
        value = value[1:]
    m = _VERSION_RE.fullmatch(value)
    if not m:
        raise ValueError("invalid version: %r" % value)
    pre = m.group(4)
    if pre:
        for part in pre.split("."):
            if part.isdigit() and len(part) > 1 and part[0] == "0":
                raise ValueError("invalid numeric prerelease identifier")
    return tuple(map(int, m.group(1, 2, 3))) + (tuple(pre.split(".")) if pre else None,)


def _cmp(a, b):
    if a[:3] != b[:3]:
        return (a[:3] > b[:3]) - (a[:3] < b[:3])
    x, y = a[3], b[3]
    if x is None or y is None:
        return 0 if x is y else (1 if x is None else -1)
    for p, q in zip(x, y):
        if p == q:
            continue
        pn, qn = p.isdigit(), q.isdigit()
        if pn and qn:
            return (int(p) > int(q)) - (int(p) < int(q))
        if pn != qn:
            return -1 if pn else 1
        return (p > q) - (p < q)
    return (len(x) > len(y)) - (len(x) < len(y))


def _partial(text):
    m = _PART_RE.fullmatch(text)
    if not m:
        raise ValueError("invalid version: %r" % text)
    raw = m.group(1, 2, 3)
    pre, build = m.group(4), m.group(5)
    if pre or build:
        if any(v in ("x", "X", "*") for v in raw if v is not None) or None in raw:
            raise ValueError("partial versions cannot have prerelease or build")
        return _parse_version(".".join(raw) + ("-" + pre if pre else "") + ("+" + build if build else "")), 3
    nums, count, wildcard = [], 0, False
    for part in raw:
        if part is None or part in ("x", "X", "*"):
            wildcard = True
        elif wildcard:
            raise ValueError("numeric component after wildcard")
        else:
            nums.append(int(part))
            count += 1
    nums.extend([0] * (3 - len(nums)))
    return tuple(nums) + (None,), count


def _upper(v, count):
    a, b, c = v[:3]
    if count <= 1:
        return (a + 1, 0, 0, ("0",))
    if count == 2:
        return (a, b + 1, 0, ("0",))
    return (a, b, c + 1, ("0",))


def _caret(v, count):
    a, b, c = v[:3]
    if a:
        return (a + 1, 0, 0, ("0",))
    if count == 1:
        return (1, 0, 0, ("0",))
    if b:
        return (0, b + 1, 0, ("0",))
    if count == 2:
        return (0, 1, 0, ("0",))
    return (0, 0, c + 1, ("0",))


def _comparator(op, text):
    if text in ("*", "x", "X"):
        if op in (">", "<"):
            return [("never", None, False)]
        if op in ("", "=", ">=", "<="):
            return []
        raise ValueError("invalid wildcard comparator")
    v, n = _partial(text)
    full = n == 3
    if op == "~":
        return [(">=", v, full), ("<", _upper(v, 1 if n <= 1 else 2), False)]
    if op == "^":
        return [(">=", v, full), ("<", _caret(v, n), False)]
    if full:
        return [(op or "=", v, True)]
    if op in ("", "="):
        return [(">=", v, False), ("<", _upper(v, n), False)]
    if op == ">=":
        return [(">=", v, False)]
    if op == ">":
        return [(">=", _upper(v, n), False)]
    if op == "<":
        return [("<", v[:3] + (("0",) if v[3] is None else v[3]), False)]
    if op == "<=":
        return [("<", _upper(v, n), False)]
    raise ValueError("invalid comparator")


def _set(source):
    source = source.strip()
    hyphen = re.fullmatch(r"(\S+)\s+-\s+(\S+)", source)
    if hyphen:
        left, ln = _partial(hyphen.group(1))
        right, rn = _partial(hyphen.group(2))
        result = [(">=", left, ln == 3)]
        result.append(("<=", right, True) if rn == 3 else ("<", _upper(right, rn), False)) if rn else None
        return result
    if not source:
        return []
    result, words, i = [], source.split(), 0
    while i < len(words):
        token = words[i]
        m = re.fullmatch(r"(>=|<=|>|<|=|\^|~)?(.*)", token)
        op, body = m.groups()
        op = op or ""
        if not body:
            i += 1
            if i == len(words) or words[i] in (">", "<", ">=", "<=", "=", "^", "~"):
                raise ValueError("missing comparator version")
            body = words[i]
        result.extend(_comparator(op, body))
        i += 1
    return result


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("range must be a string")
    result = []
    for source in range_.split("||"):
        try:
            result.append(_set(source))
        except ValueError as exc:
            raise ValueError("invalid range: %r" % range_) from exc
    return result


def _matches(v, comps):
    if any(op == "never" for op, _, _ in comps):
        return False
    for op, bound, _ in comps:
        c = _cmp(v, bound)
        if ((op == "=" and c != 0) or (op == "<" and c >= 0) or
                (op == "<=" and c > 0) or (op == ">" and c <= 0) or
                (op == ">=" and c < 0)):
            return False
    if v[3] is not None and not any(explicit and b[3] is not None and b[:3] == v[:3] for _, b, explicit in comps):
        return False
    return True


def satisfies(version: str, range_: str) -> bool:
    v = _parse_version(version)
    return any(_matches(v, comps) for comps in _parse_range(range_))


def max_satisfying(versions: list, range_: str):
    ranges = _parse_range(range_)
    best, best_v = None, None
    for value in versions:
        try:
            v = _parse_version(value)
        except (ValueError, AttributeError):
            continue
        if any(_matches(v, comps) for comps in ranges) and (best_v is None or _cmp(v, best_v) > 0):
            best, best_v = value, v
    return best
