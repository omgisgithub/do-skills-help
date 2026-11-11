"""npm-style version range matching. See TASK.md for the exact spec."""

import re


_VERSION = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
_PARTIAL = re.compile(
    r"^(0|[1-9][0-9]*|[xX*])(?:\.(0|[1-9][0-9]*|[xX*]))?"
    r"(?:\.(0|[1-9][0-9]*|[xX*]))?(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def _parse_version(text):
    text = text.strip()
    if text.startswith(("v", "=")):
        text = text[1:]
    match = _VERSION.fullmatch(text)
    if not match:
        raise ValueError("invalid version")
    major, minor, patch, pre, _build = match.groups()
    if pre:
        for ident in pre.split("."):
            if ident.isdigit() and len(ident) > 1 and ident[0] == "0":
                raise ValueError("numeric prerelease identifier has leading zero")
    return (int(major), int(minor), int(patch), tuple(pre.split(".")) if pre else None)


def _pre_cmp(a, b):
    if a is None:
        return 0 if b is None else 1
    if b is None:
        return -1
    for x, y in zip(a, b):
        if x == y:
            continue
        xn, yn = x.isdigit(), y.isdigit()
        if xn and yn:
            return -1 if int(x) < int(y) else 1
        if xn != yn:
            return -1 if xn else 1
        return -1 if x < y else 1
    return (len(a) > len(b)) - (len(a) < len(b))


def _cmp(a, b):
    for x, y in zip(a[:3], b[:3]):
        if x != y:
            return -1 if x < y else 1
    return _pre_cmp(a[3], b[3])


def _partial(text):
    text = text.strip()
    if text.startswith(("v", "=")):
        text = text[1:]
    m = _PARTIAL.fullmatch(text)
    if not m:
        raise ValueError("invalid range version")
    raw = list(m.groups()[:3])
    pre, build = m.groups()[3:]
    if (pre or build) and (any(x is None for x in raw) or
                           any(x in ("x", "X", "*") for x in raw)):
        raise ValueError("prerelease and build require a full version")
    if pre and any(x in ("x", "X", "*") for x in raw if x is not None):
        raise ValueError("partial versions cannot have prerelease")
    if build and any(x in ("x", "X", "*") for x in raw if x is not None):
        raise ValueError("partial versions cannot have build")
    vals = []
    wildcard = False
    count = 0
    for item in raw:
        if item is None:
            wildcard = True
            continue
        count += 1
        if item in ("x", "X", "*"):
            wildcard = True
        elif wildcard:
            raise ValueError("numeric component after wildcard")
        else:
            vals.append(int(item))
    while len(vals) < 3:
        vals.append(0)
    if pre:
        for ident in pre.split("."):
            if ident.isdigit() and len(ident) > 1 and ident[0] == "0":
                raise ValueError("numeric prerelease identifier has leading zero")
    return tuple(vals), count, wildcard, tuple(pre.split(".")) if pre else None


def _ver(tup):
    return (tup[0], tup[1], tup[2], None)


def _next_bound(base, count, caret=False):
    a, b, c = base
    if caret:
        if a:
            return (a + 1, 0, 0, "0")
        if count <= 1:
            return (1, 0, 0, "0")
        if b:
            return (0, b + 1, 0, "0")
        if count <= 2:
            return (0, 1, 0, "0")
        return (0, 0, c + 1, "0")
    if count <= 1:
        return (a + 1, 0, 0, "0")
    return (a, b + 1, 0, "0")


def _make_bound(op, ver, written_pre=True):
    return (op, ver, written_pre)


def _parse_comparator(token):
    m = re.fullmatch(r"(<=|>=|<|>|=)?(.*)", token)
    op, text = m.groups()
    op = op or ""
    if not text:
        raise ValueError("missing comparator version")
    base, count, wild, pre = _partial(text)
    full = count == 3 and not wild
    has_pre = pre is not None
    lower = (base[0], base[1], base[2], pre)
    if op in ("", "="):
        if full:
            return [_make_bound("=", lower, has_pre)]
        if count == 0 or (count == 1 and wild):
            return [_make_bound(">=", _ver((0, 0, 0)), False)]
        return [_make_bound(">=", _ver(base), False), _make_bound("<", _next_bound(base, count), False)]
    if not full:
        if count == 0 or wild:
            if op in (">", "<"):
                return [("!", None, False)]
            return [_make_bound(">=", _ver((0, 0, 0)), False)]
        if op == ">=":
            return [_make_bound(">=", _ver(base), False)]
        if op == ">":
            return [_make_bound(">=", _next_bound(base, count), False)]
        if op == "<":
            return [_make_bound("<", (base[0], base[1], base[2], ("0",)), False)]
        if op == "<=":
            return [_make_bound("<", _next_bound(base, count), False)]
    return [_make_bound(op, lower, has_pre)]


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("range must be a string")
    sets = []
    for rawset in range_.split("||"):
        rawset = rawset.strip()
        if not rawset:
            sets.append([])
            continue
        hyphen = re.fullmatch(r"\s*(\S+)\s+-\s+(\S+)\s*", rawset)
        if hyphen:
            left, right = _partial(hyphen.group(1)), _partial(hyphen.group(2))
            lb, lc, lw, lp = left
            rb, rc, rw, rp = right
            bounds = [_make_bound(">=", (lb[0], lb[1], lb[2], lp), lp is not None)]
            if rc == 0 or rw:
                pass
            elif rc == 3 and not rw:
                bounds.append(_make_bound("<=", (rb[0], rb[1], rb[2], rp), rp is not None))
            else:
                bounds.append(_make_bound("<", _next_bound(rb, rc), False))
            sets.append(bounds)
            continue
        # Operators may be separated from their versions by whitespace.
        pieces = rawset.split()
        tokens = []
        i = 0
        while i < len(pieces):
            part = pieces[i]
            if part in ("<", "<=", ">", ">=", "="):
                if i + 1 >= len(pieces):
                    raise ValueError("missing comparator version")
                tokens.append(part + pieces[i + 1]); i += 2
            elif part in ("~", "^"):
                if i + 1 >= len(pieces):
                    raise ValueError("missing comparator version")
                tokens.append(part + pieces[i + 1]); i += 2
            else:
                tokens.append(part); i += 1
        bounds = []
        for token in tokens:
            if token.startswith(("~", "^")):
                op, text = token[0], token[1:]
                base, count, wild, pre = _partial(text)
                if count == 0:
                    if op == "~":
                        bounds.append(_make_bound(">=", _ver((0, 0, 0)), False)); continue
                    raise ValueError("invalid caret range")
                low = (base[0], base[1], base[2], pre)
                bounds.append(_make_bound(">=", low, pre is not None))
                if op == "~":
                    upper = _next_bound(base, 1 if count == 1 else 2)
                else:
                    upper = _next_bound(base, count, True)
                bounds.append(_make_bound("<", upper, False))
            else:
                bounds.extend(_parse_comparator(token))
        sets.append(bounds)
    return sets


def _matches(version, bounds):
    for op, target, _ in bounds:
        if op == "!":
            return False
        c = _cmp(version, target)
        if not {"=": c == 0, ">": c > 0, ">=": c >= 0, "<": c < 0, "<=": c <= 0}[op]:
            return False
    if version[3] is not None:
        core = version[:3]
        if not any(written and target is not None and target[:3] == core and target[3] is not None
                   for _op, target, written in bounds):
            return False
    return True


def satisfies(version, range_):
    parsed = _parse_version(version)
    sets = _parse_range(range_)
    return any(_matches(parsed, bounds) for bounds in sets)


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best_text = None
    best = None
    for text in versions:
        try:
            parsed = _parse_version(text)
        except (ValueError, AttributeError):
            continue
        if any(_matches(parsed, bounds) for bounds in sets):
            if best is None or _cmp(parsed, best) > 0:
                best, best_text = parsed, text
    return best_text
