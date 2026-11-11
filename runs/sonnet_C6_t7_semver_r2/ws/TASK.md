# Implement version range matching in `semver_range.py`

Our package registry needs npm-style version ranges. Implement the two functions in
`semver_range.py` exactly to this spec. Python 3.9, standard library only.

## Versions
- Form: `MAJOR.MINOR.PATCH`, optionally followed by `-PRERELEASE` and/or `+BUILD`.
  MAJOR/MINOR/PATCH are non-negative integers without leading zeros (`0` is fine, `01` is not).
  PRERELEASE and BUILD are dot-separated identifiers made of `[0-9A-Za-z-]`, none empty;
  numeric prerelease identifiers must not have leading zeros.
- A single leading `v` or `=` is allowed and ignored (`v1.2.3` = `1.2.3`). Surrounding whitespace is ignored.
- BUILD is ignored for all comparisons.
- Ordering (SemVer 2.0): compare MAJOR, MINOR, PATCH numerically. A version with a prerelease
  is lower than the same version without one. Prereleases compare identifier by identifier:
  numeric identifiers compare as numbers, alphanumeric ones in ASCII order, numeric identifiers
  are always lower than alphanumeric ones, and if all shared identifiers are equal the version
  with fewer identifiers is lower (`1.0.0-alpha < 1.0.0-alpha.1 < 1.0.0-alpha.beta < 1.0.0-beta < 1.0.0-beta.2 < 1.0.0-beta.11 < 1.0.0-rc.1 < 1.0.0`).

## Ranges
A range is one or more **comparator sets** separated by `||`. A version satisfies the range if it
satisfies at least one set. A set is a whitespace-separated list of comparators; the version
must satisfy all of them. An empty set (empty string or only whitespace) means "any version".

Comparators (an operator may be followed by spaces: `>= 1.2.3` is the same as `>=1.2.3`):
- `<V`, `<=V`, `>V`, `>=V`, `=V` and a bare `V` (bare and `=` both mean exactly V).
- **Partial versions / X-ranges**: `*`, `x`, `X` are wildcards. `1.2`, `1.2.x`, `1.2.*` mean
  `>=1.2.0 <1.3.0-0`; `1`, `1.x`, `1.x.x` mean `>=1.0.0 <2.0.0-0`; `*` / `x` alone mean
  `>=0.0.0`. With operators: `>1.2` = `>=1.3.0`, `>1` = `>=2.0.0`, `>=1.2` = `>=1.2.0`,
  `<1.2` = `<1.2.0-0`, `<=1.2` = `<1.3.0-0`, `<=1` = `<2.0.0-0`, `=1.2` = `1.2`.
  `>*` and `<*` match nothing; `>=*`, `<=*` match everything (`>=0.0.0`).
  Partial versions never carry a prerelease or build.
- **Tilde**: `~1.2.3` = `>=1.2.3 <1.3.0-0`; `~1.2` = `>=1.2.0 <1.3.0-0`; `~1` = `>=1.0.0 <2.0.0-0`;
  `~0.2.3` = `>=0.2.3 <0.3.0-0`; `~1.2.3-beta.2` = `>=1.2.3-beta.2 <1.3.0-0`.
- **Caret** (do not change the left-most non-zero part):
  `^1.2.3` = `>=1.2.3 <2.0.0-0`; `^0.2.3` = `>=0.2.3 <0.3.0-0`; `^0.0.3` = `>=0.0.3 <0.0.4-0`;
  `^1.2.3-beta.2` = `>=1.2.3-beta.2 <2.0.0-0`; `^1.2` / `^1.2.x` = `>=1.2.0 <2.0.0-0`;
  `^1` / `^1.x` = `>=1.0.0 <2.0.0-0`; `^0.0` / `^0.0.x` = `>=0.0.0 <0.1.0-0`;
  `^0.x` / `^0` = `>=0.0.0 <1.0.0-0`; `^0.1` = `>=0.1.0 <0.2.0-0`.
- **Hyphen ranges** (spaces around the `-` are required): `1.2.3 - 2.3.4` = `>=1.2.3 <=2.3.4`.
  A partial left side is filled with zeros (`1.2 - 2.3.4` = `>=1.2.0 <=2.3.4`); a partial right side
  becomes an upper bound (`1.2.3 - 2.3` = `>=1.2.3 <2.4.0-0`, `1.2.3 - 2` = `>=1.2.3 <3.0.0-0`).

**Prerelease rule.** A version that has a prerelease tag (e.g. `1.2.4-alpha`) satisfies a
comparator set only if the set's comparators all match **and** at least one comparator of the set
was written with a version that has the same MAJOR.MINOR.PATCH **and** its own prerelease tag.
(The `-0` upper bounds created above by desugaring do not count for this; they only exist to
keep prereleases of the next version out.) So `1.2.4-alpha` does **not** satisfy `^1.2.3`, but
`1.2.3-beta.4` satisfies `^1.2.3-beta.2`, and `1.0.0-rc.1` does not satisfy `*`.

Anything not described here (e.g. `~>1.2`, `>=1.2.3 -`, `1.2.3.4`, `^`, `>=a.b.c`) is invalid.

## API
- `satisfies(version: str, range_: str) -> bool` — raises `ValueError` if the version or the
  range is invalid.
- `max_satisfying(versions: list, range_: str)` — the highest version string (returned exactly as
  given) that satisfies the range, or `None`. Invalid entries in `versions` are skipped; an invalid
  range raises `ValueError`. If two strings are equal in precedence (e.g. differ only in build),
  return the one that comes first in the list.
