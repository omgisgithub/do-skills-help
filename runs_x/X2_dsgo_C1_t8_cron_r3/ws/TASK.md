# Implement `next_run` in `cronexpr.py`

Our scheduler stores jobs as classic 5-field cron expressions. Implement
`next_run(expr: str, after: datetime) -> datetime` in `cronexpr.py` exactly to this spec.
Python 3.9, standard library only. Datetimes are naive (no time zones, no DST).

## Result
- Return the earliest minute (seconds and microseconds = 0) that is **strictly later** than
  `after` and matches the expression. `after` may have seconds/microseconds
  (`after = 12:00:30` → the first candidate is `12:01:00`; `after = 12:00:00` → also `12:01:00`).
- If no matching minute exists within 5 years after `after` (e.g. `0 0 30 2 *`), raise `ValueError`.
- Invalid expressions raise `ValueError`. A non-`str` expr raises `TypeError`.

## Expression
Five fields separated by one or more spaces/tabs (leading/trailing whitespace ignored):

| Field | Allowed values |
|---|---|
| minute | 0–59 |
| hour | 0–23 |
| day of month | 1–31 |
| month | 1–12 or `JAN`–`DEC` |
| day of week | 0–7 (0 and 7 are both Sunday) or `SUN`–`SAT` |

Names are case-insensitive and allowed only in their own field (also as range ends: `MON-FRI`).

Each field is a comma-separated list of items. An item is:
- `*` — every value of the field;
- `N` — a single value;
- `A-B` — inclusive range, requires `A <= B` (no wrap-around; `FRI-MON` is invalid);
- any of the above followed by `/S` (step, `S >= 1`): `*/15` = every 15th value starting at the
  field minimum, `A-B/S` = A, A+S, … up to B, and `N/S` = N, N+S, … up to the field maximum.

Values outside the field's range, empty items, `S = 0`, and anything else are invalid.
In the day-of-week field, `7` may appear anywhere a number may (`5-7` = Fri, Sat, Sun).

**Day matching.** If both the day-of-month and day-of-week fields are restricted, a day matches
when **either** of them matches. If only one is restricted, only that one counts. If neither is
restricted, every day matches. A field counts as *restricted* unless it is exactly `*`
(so `*/2` in the day-of-month field is restricted).

**Shortcuts** (the whole expression, case-insensitive): `@yearly` and `@annually` = `0 0 1 1 *`,
`@monthly` = `0 0 1 * *`, `@weekly` = `0 0 * * 0`, `@daily` and `@midnight` = `0 0 * * *`,
`@hourly` = `0 * * * *`.

## Examples
```
next_run("*/15 * * * *", datetime(2026, 3, 4, 10, 7))     -> 2026-03-04 10:15
next_run("0 9 * * MON-FRI", datetime(2026, 3, 6, 9, 0))   -> 2026-03-09 09:00   (Fri -> Mon)
next_run("0 0 29 2 *", datetime(2026, 3, 1))              -> 2028-02-29 00:00
next_run("30 4 1,15 * 5", datetime(2026, 1, 1, 5, 0))     -> 2026-01-02 04:30   (Friday)
```
