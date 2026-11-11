"""npm-style version range matching. See TASK.md for the exact spec."""

import operator
import re

_NUM = re.compile(r'0|[1-9][0-9]*')
_IDS = re.compile(r'[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*')
_OPS = {'<': operator.lt, '<=': operator.le, '>': operator.gt, '>=': operator.ge, '=': operator.eq}
_OP_SPACE = re.compile(r'(<=|>=|<|>|=|~|\^)\s+')
_COMP = re.compile(r'(<=|>=|<|>|=|~|\^)?(.*)')


def _parse(text, prefixes):
    """Return (numbers, prerelease ids). Partial versions give fewer than 3 numbers."""
    if not isinstance(text, str):
        raise ValueError(f'not a string: {text!r}')
    s = text.strip()
    if s[:1] in prefixes:
        s = s[1:]
    main, plus, build = s.partition('+')
    if plus and not _IDS.fullmatch(build):
        raise ValueError(f'bad build: {text!r}')
    main, dash, pre = main.partition('-')
    if dash and (not _IDS.fullmatch(pre) or any(i.isdigit() and i[0] == '0' and len(i) > 1 for i in pre.split('.'))):
        raise ValueError(f'bad prerelease: {text!r}')
    parts = main.split('.')
    if len(parts) > 3:
        raise ValueError(f'bad version: {text!r}')
    nums, wild = [], False
    for p in parts:
        if p in ('x', 'X', '*'):
            wild = True
        elif wild or not _NUM.fullmatch(p):
            raise ValueError(f'bad version: {text!r}')
        else:
            nums.append(int(p))
    if len(nums) < 3 and (dash or plus):
        raise ValueError(f'partial versions carry no prerelease or build: {text!r}')
    return nums, (pre.split('.') if dash else None)


def _key(nums, pre=None):
    """Sort key: a release sorts above any prerelease of the same MAJOR.MINOR.PATCH."""
    if pre is None:
        return (*nums, 1, ())
    return (*nums, 0, tuple((0, int(i)) if i.isdigit() else (1, i) for i in pre))


def _bump(nums, i):
    return nums[:i] + [nums[i] + 1] + [0] * (2 - i)


def _desugar(op, text):
    """One comparator as [(op, key, anchor)], or None if it matches nothing.
    anchor is the MAJOR.MINOR.PATCH of a written prerelease, else None."""
    nums, pre = _parse(text, ('v',))
    f = len(nums)
    lo = nums + [0] * (3 - f)
    here = _key(lo, pre)
    anchor = tuple(lo) if pre else None
    if op in ('~', '^'):
        if f == 0:
            raise ValueError(f'invalid comparator: {op}{text}')
        if op == '~':
            i = 0 if f == 1 else 1
        else:
            i = next((j for j in range(f) if nums[j]), f - 1)
        return [('>=', here, anchor), ('<', _key(_bump(lo, i), ['0']), None)]
    if f == 0:
        return None if op in ('<', '>') else [('>=', here, None)]
    full = f == 3
    if op in (None, '='):
        if full:
            return [('=', here, anchor)]
        return [('>=', here, None), ('<', _key(_bump(lo, f - 1), ['0']), None)]
    if op == '>':
        return [('>', here, anchor)] if full else [('>=', _key(_bump(lo, f - 1)), None)]
    if op == '>=':
        return [('>=', here, anchor)]
    if op == '<':
        return [('<', here, anchor)] if full else [('<', _key(lo, ['0']), None)]
    return [('<=', here, anchor)] if full else [('<', _key(_bump(lo, f - 1), ['0']), None)]


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError(f'not a string: {range_!r}')
    sets = []
    for raw in range_.split('||'):
        tokens = _OP_SPACE.sub(r'\1', raw).split()
        if len(tokens) == 3 and tokens[1] == '-':
            comps = _desugar('>=', tokens[0]) + _desugar('<=', tokens[2])
        else:
            comps = []
            for tok in tokens:
                op, text = _COMP.fullmatch(tok).groups()
                d = _desugar(op, text)
                if d is None:
                    comps = None
                    break
                comps.extend(d)
        sets.append(comps)
    return sets


def _version_key(version):
    nums, pre = _parse(version, ('v', '='))
    if len(nums) < 3:
        raise ValueError(f'not a full version: {version!r}')
    return _key(nums, pre)


def _in_set(key, comps):
    if comps is None or not all(_OPS[op](key, k) for op, k, _ in comps):
        return False
    return key[3] == 1 or any(anchor == key[:3] for _, _, anchor in comps)


def satisfies(version, range_):
    key = _version_key(version)
    return any(_in_set(key, comps) for comps in _parse_range(range_))


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = best_key = None
    for v in versions:
        try:
            key = _version_key(v)
        except ValueError:
            continue
        if (best_key is None or key > best_key) and any(_in_set(key, c) for c in sets):
            best, best_key = v, key
    return best
