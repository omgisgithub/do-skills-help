# Implement `parse_duration` in `duration.py`

Our job scheduler accepts human-written timeouts. Implement `parse_duration(s: str) -> int`,
returning a whole number of **seconds**, or raising `ValueError` for anything invalid.
Python 3.9, standard library only. Follow the grammar exactly; anything not allowed below is invalid.

## Form A: unit form
- One or more `<number><unit>` parts. Units: `w` (week, 604800 s), `d` (86400), `h` (3600),
  `m` (60), `s` (1). Lowercase only.
- `<number>` is digits, optionally with a decimal part: `1`, `10`, `1.5`, `0.25`. No leading `.`
  (`.5h` is invalid), no trailing `.` (`5.h` is invalid). Leading zeros are fine (`05m`).
- Units must appear in strictly decreasing size and each at most once (`1h30m` ok, `30m1h` and
  `1h1h` invalid).
- Parts may be separated by single spaces or written together (`1h 30m` = `1h30m`). No space
  between a number and its unit (`1 h` is invalid). No other separators.
- The total must be a whole number of seconds after exact (not floating point) arithmetic:
  `1.5m` = 90 is fine, `0.3s` is invalid, `0.1h` = 360 is fine.

## Form B: clock form
- `H:MM:SS` or `M:SS`. The first field is one or more digits with no upper limit; the other fields
  are exactly two digits and must be `00`–`59`. No decimals. `1:30` = 90, `1:00:00` = 3600,
  `90:00` = 5400, `1:60` invalid, `1:5` invalid.

## Both forms
- Leading and trailing whitespace is ignored. Inner whitespace is only allowed as in Form A.
- An optional single leading `-` makes the result negative (`-1h` = -3600, `-1:30` = -90).
  `+` is not allowed. `-0s` = 0.
- The bare string `0` is valid and means 0. Any other bare number (`5`, `1.5`) is invalid.
- Empty or whitespace-only input is invalid. Non-`str` input raises `TypeError`.

## Examples
```
parse_duration("1h30m")    -> 5400
parse_duration(" 2d 4h ")  -> 187200
parse_duration("1.5h")     -> 5400
parse_duration("1w2d3h4m5s") -> 788645
parse_duration("1:02:03")  -> 3723
parse_duration("-45s")     -> -45
parse_duration("0")        -> 0
```
