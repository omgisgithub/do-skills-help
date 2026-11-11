"""Spec checks for semver_range. Run: python3 test_semver_range.py"""

from semver_range import max_satisfying, satisfies

CASES = [
    ('1.2.3', '^1.2.3', True), ('1.2.4-alpha', '^1.2.3', False), ('1.2.3-beta.4', '^1.2.3-beta.2', True),
    ('1.0.0-rc.1', '*', False), ('2.0.0', '^1.2.3', False), ('0.2.5', '^0.2.3', True),
    ('0.3.0', '^0.2.3', False), ('0.0.3', '^0.0.3', True), ('0.0.4', '^0.0.3', False),
    ('1.2.9', '~1.2.3', True), ('1.3.0', '~1.2.3', False), ('1.2.0', '1.2', True), ('1.3.0', '1.2', False),
    ('1.9.9', '1', True), ('2.0.0', '1.x', False), ('2.3.9', '1.2.3 - 2.3', True), ('2.4.0', '1.2.3 - 2.3', False),
    ('3.0.0', '1.2.3 - 2', False), ('2.5.0', '1.2 - 2.3.4', False), ('1.2.3', '>= 1.2.3 <2', True),
    ('1.2.3', '', True), ('1.2.3', '<1.2.3 || =1.2.3', True), ('1.2.3', '>*', False), ('5.0.0', '>=*', True),
    ('1.2.3', '<*', False), ('v1.2.3', '=1.2.3', True), ('1.2.3+b', '1.2.3', True), ('1.2.3', '1.2.3+build', True),
    ('1.2.3-beta', '<1.2.3-beta.1 || >2', True), ('0.0.1', '^0.x', True), ('0.9.9', '^0', True), ('1.0.0', '^0', False),
    ('0.1.0', '^0.1', True), ('0.2.0', '^0.1', False),
]
INVALID_VERSIONS = ['01.2.3', '1.0.0-01', '1.2', 'x', '1.2.3.4', '', '=']
INVALID_RANGES = ['~>1.2', '>=1.2.3 -', '1.2.3.4', '^', '>=a.b.c', '1.x.3', '1.2.3 - 2.3.4 - 5']

for version, range_, expected in CASES:
    assert satisfies(version, range_) is expected, (version, range_)

for version in INVALID_VERSIONS:
    try:
        satisfies(version, '*')
    except ValueError:
        pass
    else:
        raise AssertionError(f'accepted invalid version {version!r}')

for range_ in INVALID_RANGES:
    try:
        satisfies('1.2.3', range_)
    except ValueError:
        pass
    else:
        raise AssertionError(f'accepted invalid range {range_!r}')

order = ['1.0.0-alpha', '1.0.0-alpha.1', '1.0.0-alpha.beta', '1.0.0-beta', '1.0.0-beta.2',
         '1.0.0-beta.11', '1.0.0-rc.1', '1.0.0']
for lower, higher in zip(order, order[1:]):
    assert max_satisfying([lower, higher], f'>={lower}') == higher, (lower, higher)

assert max_satisfying(['1.2.3', 'bogus', '1.10.0', '1.9.9+x', '1.9.9+y'], '^1') == '1.10.0'
assert max_satisfying(['1.9.9+x', '1.9.9+y'], '1.9.9') == '1.9.9+x'
assert max_satisfying(['1.0.0-rc.1'], '*') is None
assert max_satisfying(['1.0.0', '1.1.0-beta'], '*') == '1.0.0'
print('all semver_range checks passed')
