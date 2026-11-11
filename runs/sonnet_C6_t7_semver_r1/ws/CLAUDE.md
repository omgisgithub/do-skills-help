
# spec-check

Mistakes I keep seeing on these jobs, and what to do instead.

## 1. Finishing without running anything
"I did not run the script" is a failed job. Before you stop:
- Turn **every example in the spec** into an assert and run it. Copy them verbatim.
- If there is a sample input file, run your code on it and read every output row.
- Run the existing tests, if any.

## 2. Being lenient where the spec is strict
If the spec lists the accepted forms, the list is closed. Everything else is invalid.
- `Mar 4, 2026` allowed does **not** mean `Mar 4 2026` is allowed.
- Don't reach for forgiving parsers (`dateutil`, `strptime` with fallbacks, `float()`,
  `int()` on untrimmed text). Write a strict pattern per allowed form and use `re.fullmatch`.
- Read notes/comments in sample data: rows marked "bad" are telling you something.

## 3. Only testing the happy path
For each rule in the spec, write one input that must pass **and one that must fail**
(wrong case, extra space, missing part, out of range, wrong order, wrong type).
Most hidden-test failures are the negative cases nobody tried.

## 4. Overthinking
When the spec examples and your negative cases pass, stop. Don't keep deliberating.

## Checklist before you stop
- [ ] every spec example runs as an assert
- [ ] one must-fail case per rule
- [ ] sample file / existing tests run
- [ ] re-read the spec once, line by line, against the code
