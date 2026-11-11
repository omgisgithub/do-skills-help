---
name: python-coding-excellence
description: Use for small, self-contained Python jobs: implementing a function exactly to a written spec, fixing a bug in an existing module, refactoring without changing behaviour, writing a data-cleaning script, or determining exactly what a program prints or returns. Covers workflow, spec reading, edge cases, testing, verification, and common Python pitfalls.
---

# Python Coding Excellence

A working discipline for small Python tasks. The goal is code that is correct on the first delivery, minimal in footprint, and verified by actually running it, not by reasoning that it "should" work.

## Core principles

1. **The spec is the contract.** Implement what is written, not what you think is better. If the spec says return `None` on failure, do not raise. If it names a function, parameter order, or return type, match it character for character.
2. **Run it.** Anything you can execute, execute. Do not predict output when you can observe it. When you must predict (no interpreter available), trace step by step.
3. **Smallest correct change.** Fix the bug, not the neighborhood. Refactor the structure, not the behaviour. Do not reformat unrelated lines, rename unrelated things, or add dependencies.
4. **Match the surrounding code.** Naming style, comment density, quoting, type-hint usage, error-handling idiom, import ordering. A diff should look like the original author wrote it.
5. **Report honestly.** State what you ran and what happened. If a test fails or you skipped verification, say so.

## Workflow

### 1. Understand before touching anything
- Read the whole task statement once, then again, listing every concrete requirement (inputs, outputs, types, ordering, error cases, performance limits, allowed libraries, Python version).
- Read the existing file(s) fully before editing. Read the callers of anything you will change (`grep` for usages).
- Look for existing tests, docstrings, README examples, and type hints: they are secondary specs.
- Check the Python version (`python --version`) and available packages before using newer syntax (`match`, `X | Y` types, `tomllib`) or third-party libraries.
- If the spec is ambiguous in a way that changes behaviour, pick the most literal reading, state the assumption in one line, and proceed. Ask only if the choices are materially different and cannot be resolved from context.

### 2. Plan the edge cases up front
Before writing code, enumerate cases for each input:
- Empty (`""`, `[]`, `{}`, `None`, zero rows)
- Single element
- Duplicates
- Boundaries (0, 1, -1, max, exact threshold, off-by-one on `<` vs `<=`)
- Negative and zero numerics, floats vs ints, `nan`, `inf`
- Unicode, whitespace-only strings, mixed case, leading/trailing whitespace
- Already-sorted, reverse-sorted, ties
- Large inputs (is the algorithm O(n²) where n could be 10⁶?)
- Wrong types, if the spec says how to handle them

### 3. Implement
- Write the straightforward version first. Optimize only if the spec requires it or the input size demands it.
- Prefer the standard library. Reach for `collections`, `itertools`, `functools`, `re`, `datetime`, `decimal`, `fractions`, `pathlib`, `csv`, `json`, `statistics` before writing helpers.
- Keep functions pure where possible; do not mutate arguments unless the spec says to.
- Use early returns and guard clauses to keep nesting shallow.
- Add type hints and docstrings only if the surrounding code does (or the spec provides a signature to preserve).

### 4. Verify (mandatory)
- Run the spec's own examples verbatim and compare exact output.
- Write quick throwaway checks for each edge case listed in step 2.
- Run the existing test suite if there is one (`python -m pytest -q` or `python -m unittest`), before and after your change, so you can tell regressions from pre-existing failures.
- For refactors, do differential testing (see below).
- Re-read the spec one last time against the final code, line by line.

### 5. Deliver
- Show the final code or the diff, plus a short summary: what changed, what you ran, what the results were, any assumptions.
- Remove debug prints, scratch files, and temporary test code unless asked to keep them.

## Task-specific playbooks

### Implementing a function to a written spec
- Copy the signature exactly: name, parameter names, defaults, order, keyword-only markers, return annotation.
- Turn each sentence of the spec into a check. Sentences containing "must", "should", "only", "never", "at least", "at most", "unless", "otherwise" are where bugs hide.
- Decide explicitly: does it return a new object or mutate in place? A list or a generator? A tuple or a list? A `dict` with a specific key order? `int` or `float`?
- Ties and ordering: if the spec does not say, preserve input order (Python's `sorted` is stable) and say so.
- Rounding: determine whether the spec means `round()` (banker's rounding in Python 3), round-half-up (use `decimal` with `ROUND_HALF_UP`), floor, or truncation. Test with `.5` cases.
- Error handling: raise exactly the exception type the spec names, with a message if given. Do not swallow exceptions with bare `except:`.
- Do not print unless asked; return values.

### Fixing a bug in an existing module
1. **Reproduce first.** Write the smallest script or test that fails. If you cannot reproduce, you do not yet understand the bug.
2. **Locate the root cause**, not the symptom. Trace the actual values with a print or debugger (`python -m pdb`, or `breakpoint()`), then remove them.
3. **Check for siblings.** The same mistake often appears in neighboring code paths (copy-pasted logic, the mirror branch of an `if`). Fix them only if they are the same bug and clearly wrong; mention others rather than silently changing them.
4. **Make the minimal fix.** Do not rewrite the function.
5. **Confirm** the reproduction now passes, the full existing suite still passes, and add a regression test if the project has a test suite.
6. Explain the cause in one or two sentences in your summary.

Common root causes to check: off-by-one, wrong comparison operator, mutated shared default, mutation during iteration, integer vs float division, shadowed variable, wrong variable in a copy-pasted block, stale loop variable captured by closure, string vs bytes, naive vs aware datetimes, `is` used instead of `==`, truthiness check treating `0` or `""` as missing.

### Refactoring without changing behaviour
- Behaviour includes return values, exceptions raised, side effects, mutation of arguments, iteration order, and (when relevant) laziness vs eagerness. Preserve all of them, including quirks, unless told otherwise.
- Before changing anything, capture a baseline: existing tests, plus a characterization script that calls the original with many inputs (including edge cases and bad inputs) and records outputs and exceptions.
- Keep the old implementation under a temporary name and run **differential tests**: feed random and edge inputs to both and assert identical results, including identical exception types.
- Refactor in small steps, re-running checks after each.
- Do not change public names, signatures, or module-level behaviour on import. Keep re-exports if you move things.
- If you find a bug during a refactor, do not fix it silently; preserve it, and report it.

### Writing data-cleaning scripts
- Never overwrite the input. Write to a new output path, or require an explicit flag.
- Accept paths as arguments (`argparse` or `sys.argv`), not hard-coded locations, unless the spec dictates.
- Open files with explicit `encoding="utf-8"` (consider `utf-8-sig` for CSVs from Excel) and `newline=""` for `csv`.
- Use the `csv` module (or `pandas` if already in use) rather than `split(",")`; quoted fields contain commas and newlines.
- Be explicit about each cleaning rule and apply them in a documented order: strip whitespace, normalize case, normalize Unicode (`unicodedata.normalize`), parse types, handle missing values, dedupe, sort.
- Define what counts as missing (`""`, `"NA"`, `"null"`, `"N/A"`, whitespace-only) and handle it consistently.
- Parse numbers defensively: thousands separators, currency symbols, parentheses for negatives, decimal commas. Use `Decimal` for money.
- Parse dates with an explicit format; beware day/month ambiguity and time zones.
- Dedupe deliberately: decide the key, and which duplicate wins (first, last, most complete).
- Preserve row order unless sorting is specified. Preserve column order and headers.
- Do not silently drop bad rows: count them, and report or write them to a rejects file.
- Make the script idempotent: running it on its own output should change nothing.
- Print a short summary (rows in, rows out, rows dropped/changed) to stderr or stdout as appropriate.
- Test on a tiny hand-made file that includes: empty file, header only, blank lines, quoted commas, embedded newlines, duplicate rows, missing values, trailing whitespace, non-ASCII characters, and a BOM.

### Working out exactly what a program outputs
- **Run it** if you can. This is almost always the right answer. Capture stdout and stderr separately, and note the exit code.
- If you cannot run it, trace by hand with a table of variable values per step. Do not skim.
- Pay attention to exact formatting: `print` adds a newline and separates args with a space; `repr` vs `str` (strings in lists print with quotes); `print(1.0)` is `1.0`; `print(True + 1)` is `2`; float repr (`0.1 + 0.2` is `0.30000000000000004`); `round(2.5)` is `2`; `-7 // 2` is `-4`; `-7 % 3` is `2`; `int(-3.7)` is `-3`.
- Check evaluation order, short-circuiting, generator laziness, late-binding closures, mutable default arguments, aliasing (`b = a` vs `b = a[:]`; `[[0]*3]*3`), and `finally` blocks overriding returns.
- Dict order is insertion order; set order is not something to rely on (string hashing is randomized per process unless `PYTHONHASHSEED` is set).
- Report the output verbatim, including trailing whitespace and blank lines where they matter, and state whether it ended in an exception (with the traceback's final line).

## Verification toolkit

```bash
python --version
python path/to/script.py            # run it
python -c "from mod import f; print(repr(f(...)))"   # quick probe, use repr
python -m pytest -q                  # or: python -m unittest -v
python -m doctest -v mod.py          # if docstrings contain examples
python -m py_compile mod.py          # syntax check
python -W error script.py            # surface warnings as errors
```

- Use `repr()` when inspecting values, so whitespace, quotes, and types are visible.
- Use `assert` statements with explicit expected values in throwaway checks; compare whole structures, not pieces.
- For properties, test invariants on random inputs: length preserved, output sorted, idempotence, round-trip (`decode(encode(x)) == x`), agreement with a slow-but-obviously-correct reference.
- Seed randomness (`random.seed(0)`) so failures reproduce.
- If a linter or formatter is configured in the project (ruff, black, flake8, mypy), run it on the files you touched. Do not introduce a new tool.

## Common pitfalls (checklist)

**Mutability and state**
- Mutable default arguments (`def f(x=[])`): use `None` and create inside.
- Mutating a list while iterating over it: iterate over a copy or build a new list.
- Shallow vs deep copy: `list(a)`/`a.copy()` do not copy nested objects.
- `[[0] * n] * m` creates aliased rows; use a comprehension.
- Modifying an argument the caller still uses.

**Numbers**
- `/` is true division; `//` floors toward negative infinity; `%` takes the sign of the divisor.
- Banker's rounding in `round()`; float representation errors in equality (`math.isclose`, or `Decimal`).
- `bool` is a subclass of `int`: `isinstance(True, int)` is `True`; `sum([True, True])` is `2`.
- `nan != nan`; `nan` in sorts and `min`/`max` gives inconsistent results.
- Integer parsing: `int("1_000")` works, `int(" 5 ")` works, `int("5.0")` raises.

**Strings and text**
- `str.strip(chars)` removes a set of characters, not a prefix/suffix; use `removeprefix`/`removesuffix` (3.9+).
- `split()` with no args collapses whitespace; `split(" ")` does not.
- `str.lower()` vs `casefold()` for comparisons.
- Regex: raw strings, greedy vs lazy, `match` anchors at start only, `fullmatch` for whole string, `re.escape` for literals, flags for `^`/`$` with multiline.
- Slicing never raises for out-of-range; indexing does.
- Bytes vs str; always specify encodings.

**Control flow and logic**
- `if x:` vs `if x is not None:` when `0`, `""`, `[]` are valid values.
- `is` for identity only (`None`, sentinels); never for numbers or strings.
- `and`/`or` return operands, not booleans.
- Chained comparisons (`a < b < c`) are valid and short-circuit.
- `any([])` is `False`, `all([])` is `True`; `max([])` raises unless `default=` is given.
- A bare `except:` or `except Exception: pass` hides bugs.
- `for ... else` runs `else` when no `break` occurred.
- Closures in loops capture variables, not values: bind with a default argument.
- Generators are single-use; `zip` stops at the shortest (`strict=True` in 3.10+); `map`/`filter` are lazy.

**Collections**
- Dict key order is insertion order; deleting during iteration raises `RuntimeError`.
- `dict.get(k, default)` evaluates the default eagerly; `setdefault` and `defaultdict` have side effects on read.
- Unhashable types (lists, dicts) cannot be dict keys or set members.
- `sorted` is stable; `key=` is better than `cmp`; `reverse=True` preserves stability of equal elements, while `reversed(sorted(...))` does not.
- `list.sort()` returns `None`.
- `copy` vs reference when storing the same list in multiple dict values.

**Files, dates, and environment**
- Use `pathlib.Path` and context managers (`with open(...)`).
- Naive vs timezone-aware `datetime` cannot be compared; `datetime.utcnow()` is deprecated, so use `datetime.now(timezone.utc)`.
- `strptime` format codes are case-sensitive (`%m` month vs `%M` minute).
- Relative paths depend on the current working directory.
- Do not leave `print` debugging, `breakpoint()`, or scratch files in the deliverable.

## Style and quality bar
- Readable beats clever. A clear loop is better than a nested comprehension that needs a comment.
- Names describe meaning (`unpaid_invoices`, not `lst2`).
- One function, one job; keep functions short enough to read at once.
- Comments explain why, not what. Match the existing comment density.
- Avoid global state and import-time side effects; guard scripts with `if __name__ == "__main__":`.
- Do not add features, logging, CLI flags, or abstractions that were not requested.
- Handle errors at the right level: validate inputs at boundaries, let unexpected errors propagate with a clear traceback.

## Performance
- Correctness first. Only optimize when the spec states limits or inputs are clearly large.
- Common wins: use a `set` or `dict` for membership instead of list scans, `collections.Counter`/`deque`/`heapq`/`bisect`, avoid repeated string concatenation in loops (`"".join`), compute once outside loops, stream large files line by line instead of reading everything.
- Measure with `timeit` or a quick timing script before and after; do not guess.

## Final checklist before replying
- [ ] Signature, names, and return types match the spec exactly
- [ ] Every requirement sentence maps to code and to a check
- [ ] Spec examples run and match exactly
- [ ] Edge cases (empty, single, boundary, duplicates, bad input) tested
- [ ] Existing tests pass; no new regressions; refactors differentially tested
- [ ] Diff is minimal and matches the surrounding style
- [ ] No debug output, scratch files, or unrequested features left behind
- [ ] Summary states what was run, results observed, and any assumptions or noticed-but-untouched issues
