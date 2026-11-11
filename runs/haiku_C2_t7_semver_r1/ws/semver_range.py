"""npm-style version range matching. See TASK.md for the exact spec."""

import operator
import re

_NUM = re.compile(r'0|[1-9][0-9]*')
_IDENT = re.compile(r'[0-9A-Za-z-]+')
_WILD = ('x', 'X', '*')
_OP = re.compile(r'(<=|>=|<|>|=|~|\^)?(.*)', re.S)
_CMP = {'<': operator.lt, '<=': operator.le, '>': operator.gt, '>=': operator.ge, '=': operator.eq}
_NOTHING = (0, 0, 0, 0, ())  # sorts below every version, so `<` against it matches nothing


def _ids_ok(text, no_leading_zero):
    for ident in text.split('.'):
        if not _IDENT.fullmatch(ident):
            return False
        if no_leading_zero and ident.isdigit() and len(ident) > 1 and ident[0] == '0':
            return False
    return True


def _pre_key(text):
    return tuple((0, int(i), '') if i.isdigit() else (1, 0, i) for i in text.split('.'))


def _at(t):  # lowest version with major.minor.patch t
    return t + (1, ())


def _below(t):  # `t-0`: sorts below every prerelease of t
    return t + (0, ((0, 0, ''),))


def _next(k, nums):  # first version past an x-range with k given parts
    M, m, _ = nums
    return (M + 1, 0, 0) if k == 1 else (M, m + 1, 0)


def _parse(text):
    """-> (k, nums, key, anchor): k numeric parts given (0-3), nums zero-padded to 3.
    key is the precedence key (full versions only); anchor is nums when the version has a prerelease."""
    if not isinstance(text, str):
        raise ValueError(text)
    text = text.strip()
    if text[:1] in ('v', '='):
        text = text[1:]
    text, plus, build = text.partition('+')
    core, dash, pre = text.partition('-')
    parts = core.split('.')
    if plus and not _ids_ok(build, False):
        raise ValueError(text)
    if len(parts) != 3 or any(p in _WILD for p in parts):
        if dash or plus or len(parts) > 3:
            raise ValueError(text)
        nums = []
        for i, p in enumerate(parts):
            if p in _WILD:
                if any(q not in _WILD for q in parts[i:]):
                    raise ValueError(text)
                break
            if not _NUM.fullmatch(p):
                raise ValueError(text)
            nums.append(int(p))
        return len(nums), tuple(nums + [0] * (3 - len(nums))), None, None
    if not all(_NUM.fullmatch(p) for p in parts):
        raise ValueError(text)
    nums = tuple(int(p) for p in parts)
    if not dash:
        return 3, nums, nums + (1, ()), None
    if not _ids_ok(pre, True):
        raise ValueError(text)
    return 3, nums, nums + (0, _pre_key(pre)), nums


def _comparator(text):
    """One comparator -> list of (op, bound, anchor). anchor: see _in_set."""
    op, rest = _OP.fullmatch(text).groups()
    op = op or ''
    if rest[:1] in ('<', '>', '=', '~', '^'):
        raise ValueError(text)
    if op in ('~', '^'):
        return _tilde_caret(op, rest)
    k, nums, key, anchor = _parse(rest)
    if k == 3:
        return [(op or '=', key, anchor)]
    if k == 0:  # `*`, `x`
        return [('<', _NOTHING, None)] if op in ('<', '>') else [('>=', _at((0, 0, 0)), None)]
    if op in ('', '='):
        return [('>=', _at(nums), None), ('<', _below(_next(k, nums)), None)]
    if op == '>=':
        return [('>=', _at(nums), None)]
    if op == '<':
        return [('<', _below(nums), None)]
    if op == '<=':
        return [('<', _below(_next(k, nums)), None)]
    return [('>=', _at(_next(k, nums)), None)]  # '>'


def _tilde_caret(op, text):
    k, nums, key, anchor = _parse(text)
    M, m, p = nums
    if k == 0:
        raise ValueError(text)
    if op == '~':
        up = _next(k, nums)
    elif k == 1 or M > 0:
        up = (M + 1, 0, 0)
    elif k == 2 or m > 0:
        up = (0, m + 1, 0)
    else:
        up = (0, 0, p + 1)
    return [('>=', key if k == 3 else _at(nums), anchor), ('<', _below(up), None)]


def _hyphen(a, b):
    if a[:1] in ('<', '>', '=', '~', '^') or b[:1] in ('<', '>', '=', '~', '^'):
        raise ValueError(f'{a} - {b}')
    k1, n1, key1, anchor1 = _parse(a)
    k2, n2, key2, anchor2 = _parse(b)
    hi = [('<=', key2, anchor2)] if k2 == 3 else [('<', _below(_next(k2, n2)), None)] if k2 else []
    return [('>=', key1 if k1 == 3 else _at(n1), anchor1)] + hi


def _set(text):
    tokens = text.split()
    if '-' in tokens:
        if len(tokens) != 3 or tokens[1] != '-':
            raise ValueError(text)
        return _hyphen(tokens[0], tokens[2])
    comps, i = [], 0
    while i < len(tokens):
        item = tokens[i]
        if item in _CMP and i + 1 < len(tokens):  # `>= 1.2.3`
            i += 1
            item += tokens[i]
        comps += _comparator(item)
        i += 1
    return comps


def _in_set(key, comps):
    if not all(_CMP[op](key, bound) for op, bound, _ in comps):
        return False
    # prerelease rule: needs a comparator written as the same M.m.p with a prerelease
    return key[3] == 1 or any(anchor == key[:3] for _, _, anchor in comps)


def _sets(range_):
    return [_set(s) for s in range_.split('||')]


def satisfies(version, range_):
    k, _, key, _ = _parse(version)
    if k != 3:
        raise ValueError(version)
    return any(_in_set(key, s) for s in _sets(range_))


def max_satisfying(versions, range_):
    sets = _sets(range_)
    best = None
    for v in versions:
        try:
            k, _, key, _ = _parse(v)
        except ValueError:
            continue
        if k == 3 and any(_in_set(key, s) for s in sets) and (best is None or key > best[0]):
            best = (key, v)
    return None if best is None else best[1]
