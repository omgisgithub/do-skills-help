"""npm-style version range matching. See TASK.md for the exact spec."""

import re
from functools import cmp_to_key


_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$")
_PARTIAL = re.compile(r"^(0|[1-9][0-9]*)(?:\.(0|[1-9][0-9]*|[xX*]))?(?:\.(0|[1-9][0-9]*|[xX*]))?(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$")


def _version(value):
    if not isinstance(value, str):
        raise ValueError("version must be a string")
    value = value.strip()
    if value[:1] in ("v", "="):
        value = value[1:]
    m = _VERSION.fullmatch(value)
    if not m:
        raise ValueError("invalid version: %r" % value)
    pre = m.group(4)
    if pre and any(x.isdigit() and len(x) > 1 and x[0] == "0" for x in pre.split(".")):
        raise ValueError("invalid numeric prerelease identifier")
    return (int(m[1]), int(m[2]), int(m[3])), tuple(pre.split(".")) if pre else ()


def _cmp(a, b):
    if a[0] != b[0]:
        return (a[0] > b[0]) - (a[0] < b[0])
    x, y = a[1], b[1]
    if not x or not y:
        return 0 if x == y else (1 if not x else -1)
    for p, q in zip(x, y):
        if p == q:
            continue
        pn, qn = p.isdigit(), q.isdigit()
        if pn != qn:
            return -1 if pn else 1
        if pn:
            return (int(p) > int(q)) - (int(p) < int(q))
        return (p > q) - (p < q)
    return (len(x) > len(y)) - (len(x) < len(y))


def _partial(text):
    text = text.strip()
    if text in ("*", "x", "X"):
        return [None, None, None], ()
    if text[:1] in ("v", "="):
        text = text[1:]
    m = _PARTIAL.fullmatch(text)
    if not m:
        raise ValueError("invalid range version: %r" % text)
    vals = list(m.group(i) for i in (1, 2, 3))
    wildcard = False
    nums = []
    for v in vals:
        if v is None or v in ("x", "X", "*"):
            wildcard = True
            nums.append(None)
        elif wildcard:
            raise ValueError("invalid partial version")
        else:
            nums.append(int(v))
    pre = m.group(4)
    if pre and (wildcard or nums[1] is None or nums[2] is None):
        raise ValueError("partial versions cannot have prereleases")
    if pre and any(x.isdigit() and len(x) > 1 and x[0] == "0" for x in pre.split(".")):
        raise ValueError("invalid numeric prerelease identifier")
    return nums, tuple(pre.split(".")) if pre else ()


def _parse_set(source):
    source = source.strip()
    if not source:
        return [], False
    # Hyphen ranges need their spaces; recognize them before tokenizing comparators.
    hyphen = re.fullmatch(r"(.+?)\s+-\s+(.+)", source)
    if hyphen:
        left, left_pre = _partial(hyphen[1]); right, right_pre = _partial(hyphen[2])
        out = []
        lo = tuple(0 if n is None else n for n in left)
        out.append((">=", (lo, left_pre if all(n is not None for n in left) else ())))
        if right[1] is None:
            if right[0] is not None:
                out.append(("<", ((right[0] + 1, 0, 0), ("0",))))
        elif right[2] is None:
            out.append(("<", ((right[0], right[1] + 1, 0), ("0",))))
        else:
            out.append(("<=", (tuple(right), right_pre)))
        return out, False

    # Join a separated comparator with its operand, while leaving ordinary whitespace as AND.
    words = source.split()
    tokens = []
    i = 0
    while i < len(words):
        if words[i] in ("<", "<=", ">", ">=", "=", "~", "^"):
            if i + 1 == len(words): raise ValueError("missing comparator operand")
            tokens.append(words[i] + words[i + 1]); i += 2
        else:
            tokens.append(words[i]); i += 1
    out, impossible = [], False
    for token in tokens:
        m = re.match(r"^(<=|>=|<|>|=|~|\^)?(.*)$", token)
        op, body = m[1] or "", m[2]
        if not body: raise ValueError("missing comparator operand")
        vals, pre = _partial(body)
        n = sum(v is not None for v in vals)
        full = n == 3
        ver = (tuple(0 if v is None else v for v in vals), pre)
        if op in ("~", "^"):
            if n == 0:
                if op == "^": continue
                raise ValueError("invalid tilde range")
            lo = ver
            if op == "~":
                upper = (vals[0] + 1, 0, 0) if n == 1 else (vals[0], vals[1] + 1, 0)
            elif vals[0] != 0:
                upper = (vals[0] + 1, 0, 0)
            elif n == 1:
                upper = (1, 0, 0)
            elif vals[1] != 0:
                upper = (0, vals[1] + 1, 0)
            elif n == 2:
                upper = (0, 1, 0)
            elif vals[2] != 0:
                upper = (0, 0, vals[2] + 1)
            else:
                upper = (0, 0, 1)
            out.extend(((">=", lo), ("<", (upper, ("0",)))))
        elif n == 0:
            if op in (">", "<"):
                impossible = True
        elif full:
            out.append((op or "=", ver))
        else:
            lower = ver
            if op in ("", "=", ">="):
                if op in ("", "="):
                    if n == 3: out.append(("=", lower))
                    else:
                        upper = (vals[0] + 1, 0, 0) if n == 1 else (vals[0], vals[1] + 1, 0)
                        out.extend(((">=", lower), ("<", (upper, ("0",)))))
                else: out.append((">=", lower))
            elif op == ">":
                upper = (vals[0] + 1, 0, 0) if n == 1 else (vals[0], vals[1] + 1, 0)
                out.append((">=", (upper, ())))
            elif op == "<": out.append(("<", (lower[0], ("0",))))
            elif op == "<=":
                upper = (vals[0] + 1, 0, 0) if n == 1 else (vals[0], vals[1] + 1, 0)
                out.append(("<", (upper, ("0",))))
    return out, impossible


def _range(range_):
    if not isinstance(range_, str): raise ValueError("range must be a string")
    sets = []
    for source in range_.split("||"):
        if "|" in source: raise ValueError("invalid range")
        sets.append(_parse_set(source))
    return sets


def _matches(version, parsed):
    for comps, impossible in parsed:
        if impossible: continue
        ok = True
        prerelease_allowed = False
        for op, bound in comps:
            c = _cmp(version, bound)
            if not ((op == "<" and c < 0) or (op == "<=" and c <= 0) or
                    (op == ">" and c > 0) or (op == ">=" and c >= 0) or
                    (op == "=" and c == 0)):
                ok = False; break
            if bound[1] and bound[0] == version[0]: prerelease_allowed = True
        if ok and (not version[1] or prerelease_allowed): return True
    return False


def satisfies(version, range_):
    return _matches(_version(version), _range(range_))


def max_satisfying(versions, range_):
    parsed = _range(range_)
    best, best_v = None, None
    for version in versions:
        try: parsed_v = _version(version)
        except (ValueError, TypeError): continue
        if _matches(parsed_v, parsed) and (best_v is None or _cmp(parsed_v, best_v) > 0):
            best, best_v = version, parsed_v
    return best
