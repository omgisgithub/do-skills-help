"""npm-style version range matching. See TASK.md for the exact spec."""

import operator
import re

_IDS = r"[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*"
_CORE_RE = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-(" + _IDS + r"))?(?:\+" + _IDS + r")?"
)
_PARTIAL_RE = re.compile(r"(0|[1-9][0-9]*|[xX*])(?:\.(0|[1-9][0-9]*|[xX*])(?:\.(0|[1-9][0-9]*|[xX*]))?)?")
_COMPARATOR_RE = re.compile(r"(<=|>=|<|>|=|~|\^)?(.*)", re.S)
_OPERATORS = ("<", "<=", ">", ">=", "=", "~", "^")
_COMPARE = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge, "=": operator.eq}
_NEVER = "never"
_ZERO = ("0",)  # the "-0" prerelease used by desugared upper bounds


def _key(major, minor, patch, pre=None):
    """Precedence key: release versions sort above any prerelease of the same MAJOR.MINOR.PATCH."""
    if pre is None:
        tail = (1,)
    else:
        tail = (0, tuple((0, int(i)) if i.isdigit() else (1, i) for i in pre))
    return (major, minor, patch, tail)


def _parse_version_core(text):
    """Parse a full MAJOR.MINOR.PATCH[-pre][+build] string into (major, minor, patch, pre), or None."""
    m = _CORE_RE.fullmatch(text)
    if m is None:
        return None
    pre = m.group(4)
    if pre is not None:
        pre = tuple(pre.split("."))
        for ident in pre:
            if ident.isdigit() and len(ident) > 1 and ident[0] == "0":
                return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), pre


def _parse_version(text):
    if not isinstance(text, str):
        raise ValueError("version must be a string: %r" % (text,))
    s = text.strip()
    if s[:1] in ("v", "="):
        s = s[1:]
    parsed = _parse_version_core(s)
    if parsed is None:
        raise ValueError("invalid version: %r" % (text,))
    return parsed


def _parse_comparator(token):
    """Split a comparator token into (op, major, minor, patch, pre); missing or wildcard parts are None."""
    m = _COMPARATOR_RE.fullmatch(token)
    op, rest = m.group(1) or "", m.group(2)
    if rest[:1] == "v":
        rest = rest[1:]
    core = _parse_version_core(rest)
    if core is not None:
        return (op,) + core
    p = _PARTIAL_RE.fullmatch(rest)
    if p is None:
        raise ValueError("invalid comparator: %r" % (token,))
    nums = []
    wild = False
    for g in (g for g in p.groups() if g is not None):
        if g in ("x", "X", "*"):
            wild = True
            nums.append(None)
        elif wild:
            raise ValueError("invalid comparator: %r" % (token,))
        else:
            nums.append(int(g))
    nums += [None] * (3 - len(nums))
    return (op, nums[0], nums[1], nums[2], None)


def _comparator_atoms(op, major, minor, patch, pre):
    """Desugar one comparator into ((op, bound), ...) atoms plus the MMP it anchors on, if any."""
    anchor = (major, minor, patch) if pre is not None else None

    if major is not None and minor is not None and patch is not None:
        bound = _key(major, minor, patch, pre)
        if op in ("", "="):
            return [("=", bound)], anchor
        if op in ("<", "<=", ">", ">="):
            return [(op, bound)], anchor
        if op == "~":
            return [(">=", bound), ("<", _key(major, minor + 1, 0, _ZERO))], anchor
        # caret: keep the left-most non-zero part fixed
        if major > 0:
            hi = _key(major + 1, 0, 0, _ZERO)
        elif minor > 0:
            hi = _key(0, minor + 1, 0, _ZERO)
        else:
            hi = _key(0, 0, patch + 1, _ZERO)
        return [(">=", bound), ("<", hi)], anchor

    if major is None:
        if op in (">", "<"):
            return [(_NEVER, None)], None
        return [(">=", _key(0, 0, 0))], None

    if minor is None:
        lo = _key(major, 0, 0)
        if op in ("", "=", "~", "^"):
            return [(">=", lo), ("<", _key(major + 1, 0, 0, _ZERO))], None
        if op == ">=":
            return [(">=", lo)], None
        if op == ">":
            return [(">=", _key(major + 1, 0, 0))], None
        if op == "<":
            return [("<", _key(major, 0, 0, _ZERO))], None
        return [("<", _key(major + 1, 0, 0, _ZERO))], None  # "<="

    lo = _key(major, minor, 0)
    if op in ("", "=", "~"):
        return [(">=", lo), ("<", _key(major, minor + 1, 0, _ZERO))], None
    if op == "^":
        hi = _key(major + 1, 0, 0, _ZERO) if major > 0 else _key(0, minor + 1, 0, _ZERO)
        return [(">=", lo), ("<", hi)], None
    if op == ">=":
        return [(">=", lo)], None
    if op == ">":
        return [(">=", _key(major, minor + 1, 0))], None
    if op == "<":
        return [("<", _key(major, minor, 0, _ZERO))], None
    return [("<", _key(major, minor + 1, 0, _ZERO))], None  # "<="


def _parse_hyphen_end(text):
    """Parse one side of a hyphen range: a full version, or a wildcard-free partial version."""
    s = text[1:] if text[:1] == "v" else text
    core = _parse_version_core(s)
    if core is not None:
        return core
    p = _PARTIAL_RE.fullmatch(s)
    if p is None or re.search(r"[xX*]", s):
        raise ValueError("invalid hyphen range endpoint: %r" % (text,))
    nums = [int(g) for g in p.groups() if g is not None]
    nums += [None] * (3 - len(nums))
    return nums[0], nums[1], nums[2], None


def _hyphen_set(low, high):
    major, minor, patch, pre = _parse_hyphen_end(low)
    atoms = [(">=", _key(major, minor or 0, patch or 0, pre))]
    anchors = {(major, minor, patch)} if pre is not None else set()

    major, minor, patch, pre = _parse_hyphen_end(high)
    if minor is None:
        atoms.append(("<", _key(major + 1, 0, 0, _ZERO)))
    elif patch is None:
        atoms.append(("<", _key(major, minor + 1, 0, _ZERO)))
    else:
        atoms.append(("<=", _key(major, minor, patch, pre)))
        if pre is not None:
            anchors.add((major, minor, patch))
    return atoms, anchors


def _parse_set(text):
    """Parse one comparator set into (atoms, anchors)."""
    tokens = text.split()
    if not tokens:
        return [], set()
    if "-" in tokens:
        if len(tokens) != 3 or tokens[1] != "-":
            raise ValueError("invalid hyphen range: %r" % (text,))
        return _hyphen_set(tokens[0], tokens[2])

    atoms, anchors = [], set()
    i = 0
    while i < len(tokens):
        token = tokens[i]
        i += 1
        if token in _OPERATORS:  # an operator may be separated from its version by spaces
            if i >= len(tokens):
                raise ValueError("operator without version: %r" % (text,))
            token += tokens[i]
            i += 1
        comp_atoms, anchor = _comparator_atoms(*_parse_comparator(token))
        atoms.extend(comp_atoms)
        if anchor is not None:
            anchors.add(anchor)
    return atoms, anchors


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("range must be a string: %r" % (range_,))
    return [_parse_set(part) for part in range_.split("||")]


def _set_matches(atoms, anchors, version):
    major, minor, patch, pre = version
    # A prerelease only matches if some written comparator has the same MAJOR.MINOR.PATCH and a prerelease.
    if pre is not None and (major, minor, patch) not in anchors:
        return False
    key = _key(major, minor, patch, pre)
    for op, bound in atoms:
        if op == _NEVER or not _COMPARE[op](key, bound):
            return False
    return True


def satisfies(version, range_):
    parsed = _parse_version(version)
    sets = _parse_range(range_)
    return any(_set_matches(atoms, anchors, parsed) for atoms, anchors in sets)


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = None
    best_key = None
    for item in versions:
        try:
            parsed = _parse_version(item)
        except ValueError:
            continue
        if not any(_set_matches(atoms, anchors, parsed) for atoms, anchors in sets):
            continue
        key = _key(*parsed)
        if best_key is None or key > best_key:
            best, best_key = item, key
    return best
