# Cron next-run implementation plan

**Goal:** Implement `next_run(expr: str, after: datetime) -> datetime` to TASK.md.
**Architecture:** Expand validated fields to sets, preserving whether each day
field is exactly `*`. Search dates in order with sorted allowed times to avoid
scanning millions of minutes for impossible schedules.
**Tech stack:** Python 3.9, standard library only.
**Spec:** TASK.md.

## Steps

- [x] Add public-API unittest cases for the examples, strict minute advancement,
  steps, names, Sunday aliases, day OR semantics, shortcuts, invalid syntax,
  impossible dates, leap years, and datetime limits.
- [x] Run `python3 -m unittest -v` and confirm the stub fails those cases.
- [x] Implement field validation, expansion, and bounded date search in cronexpr.py.
- [x] Run the full unittest suite and compare randomized schedules against an
  independent minute-by-minute reference.

## Verification

All 9 unittest methods pass on Python 3.9.6. An independent minute-by-minute
reference agreed on 200 seeded randomized schedules. Read-only code review
found no correctness bugs or missing requirements.

## Boundary decisions

The five-year limit is the calendar anniversary, inclusive; a February 29
anniversary in a non-leap year is February 28. Search ends at datetime.max when
the anniversary exceeds the datetime range. Invalid syntax must be rejected
even when another list item already selects all values. Sunday normalization
happens after expanding ranges and steps, so numeric 7 retains its endpoint
meaning during expansion.
