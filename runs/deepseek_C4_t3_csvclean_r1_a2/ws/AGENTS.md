# AGENTS.md

> This file guides AI coding agents (Claude Code, Codex, Cursor, Copilot, and similar) working in this repository. It is also symlinked as `CLAUDE.md`. Humans should read it too: it is the canonical summary of how we build software here.

---

## 1. Project Overview

**Project name:** `acme-service`
**Language:** Python 3.12+
**Purpose:** A backend service that ingests events from upstream producers, validates and enriches them, persists them to PostgreSQL, and exposes a REST API (FastAPI) and a background worker (Celery) for downstream consumers.

### Goals

- Correctness first, then readability, then performance.
- Small, reviewable changes with tests.
- Boring, well-understood technology over clever abstractions.

### Non-goals

- This repo is not a general-purpose framework. Avoid building reusable abstractions until there are at least three concrete users.
- We do not support Python versions below 3.12.

### Key technologies

| Concern            | Choice                          |
|--------------------|---------------------------------|
| Web framework      | FastAPI                         |
| ORM / DB           | SQLAlchemy 2.x (async), Alembic |
| Database           | PostgreSQL 16                   |
| Task queue         | Celery + Redis                  |
| Validation         | Pydantic v2                     |
| Packaging          | `uv` + `pyproject.toml`         |
| Lint / format      | Ruff                            |
| Type checking      | mypy (strict) or pyright        |
| Testing            | pytest, pytest-asyncio, hypothesis |
| CI                 | GitHub Actions                  |

---

## 2. Quick Start

```bash
# Install dependencies (creates .venv automatically)
uv sync --all-extras

# Activate the environment
source .venv/bin/activate

# Start local infrastructure (Postgres, Redis)
docker compose up -d

# Apply migrations
make migrate

# Run the API with reload
make dev

# Run the worker
make worker
```

### Common commands

| Command            | What it does                                    |
|--------------------|-------------------------------------------------|
| `make fmt`         | Format with Ruff                                |
| `make lint`        | Ruff lint (no autofix)                          |
| `make typecheck`   | Run mypy over `src/` and `tests/`               |
| `make test`        | Run the full test suite                         |
| `make test-fast`   | Unit tests only, no external services           |
| `make cov`         | Tests with coverage report                      |
| `make check`       | fmt-check + lint + typecheck + test (CI parity) |
| `make migrate`     | Apply Alembic migrations                        |
| `make revision m="msg"` | Autogenerate a migration                   |

Always prefer the `make` targets over invoking tools directly, so your results match CI.

---

## 3. Architecture

The service follows a **layered architecture** with dependencies pointing inward:

```
        ┌──────────────────────────┐
        │   api / worker (entry)   │   HTTP handlers, Celery tasks
        └────────────┬─────────────┘
                     │
        ┌────────────▼─────────────┐
        │        services          │   Business logic, orchestration
        └────────────┬─────────────┘
                     │
        ┌────────────▼─────────────┐
        │  repositories / clients  │   DB access, external APIs
        └────────────┬─────────────┘
                     │
        ┌────────────▼─────────────┐
        │     domain (models)      │   Pure types, no I/O
        └──────────────────────────┘
```

### Layer rules

1. **Domain** has no imports from other layers and performs no I/O.
2. **Repositories/clients** may import from domain only.
3. **Services** may import from domain, repositories, and clients. They never import from `api` or `worker`.
4. **API and worker** are thin. They parse input, call a service, and format output. No business logic.
5. Cross-layer imports upward are forbidden and enforced by `import-linter` (see `pyproject.toml`).

### Key design decisions

- **Async by default** for I/O paths. Sync code is acceptable only for CPU-bound work or in Celery tasks that wrap sync libraries.
- **Dependency injection** via FastAPI `Depends` at the edge and explicit constructor arguments inside services. No global singletons, no module-level clients.
- **Repository pattern** isolates SQLAlchemy. Services never build queries.
- **Pydantic models** are used at boundaries (API schemas, config, event payloads). Internal domain objects are frozen dataclasses unless validation is needed.
- **Idempotency:** every worker task and ingestion endpoint must be safe to retry.
- **Transactions** are managed at the service layer through a unit-of-work object, not in repositories.

---

## 4. Directory Layout

```
.
├── AGENTS.md                  # This file (CLAUDE.md symlinks here)
├── README.md
├── pyproject.toml             # Single source of truth for deps and tool config
├── uv.lock                    # Locked dependencies (commit this)
├── Makefile
├── docker-compose.yml
├── alembic.ini
├── .github/
│   ├── workflows/             # CI definitions
│   ├── CODEOWNERS
│   └── pull_request_template.md
├── docs/
│   ├── architecture.md
│   ├── adr/                   # Architecture Decision Records
│   └── runbooks/
├── migrations/
│   ├── env.py
│   └── versions/
├── src/
│   └── acme_service/
│       ├── __init__.py
│       ├── py.typed
│       ├── config.py          # Pydantic Settings
│       ├── logging.py         # Logging setup
│       ├── errors.py          # Exception hierarchy
│       ├── domain/            # Pure models and value objects
│       ├── repositories/      # DB access
│       ├── clients/           # External HTTP/API clients
│       ├── services/          # Business logic
│       ├── api/
│       │   ├── app.py         # FastAPI factory
│       │   ├── deps.py        # Dependency providers
│       │   ├── routers/
│       │   └── schemas/       # Request/response models
│       └── worker/
│           ├── app.py         # Celery app
│           └── tasks/
├── tests/
│   ├── conftest.py
│   ├── unit/                  # Mirrors src/ layout
│   ├── integration/           # Real Postgres/Redis via docker
│   ├── e2e/                   # Full-stack API tests
│   └── factories/             # Test data builders
└── scripts/                   # One-off operational scripts
```

### Placement rules

- New code goes in `src/acme_service/`. Never add importable code at the repo root.
- Test files mirror the source path: `src/acme_service/services/billing.py` → `tests/unit/services/test_billing.py`.
- Scripts in `scripts/` must not be imported by application code.
- Do not create new top-level directories without discussion.

---

## 5. Coding Standards

### General principles

- **Readability over cleverness.** Write code a tired teammate can understand at 2 a.m.
- **Explicit is better than implicit.** Avoid magic, metaprogramming, and monkeypatching in production code.
- **Small functions.** Aim for under 40 lines and a single level of abstraction. Extract when a function does more than one thing.
- **Shallow nesting.** Prefer early returns and guard clauses over deep `if` trees.
- **Immutability by default.** Use `frozen=True` dataclasses, tuples, and `frozenset` where mutation isn't needed.
- **No dead code.** Delete unused functions, imports, and commented-out blocks. Git remembers.
- **Match the surrounding code.** When editing an existing file, follow its conventions for comment density, naming, and idiom, unless the file violates this document.

### Formatting

- Ruff is the formatter and linter. Line length is **100**.
- Do not hand-format. Run `make fmt`.
- Imports are sorted by Ruff (isort rules): stdlib, third-party, first-party, local.
- Use absolute imports (`from acme_service.services import billing`). Relative imports are allowed only within the same package for siblings.
- Never use wildcard imports.

### Language features

- Use `pathlib.Path`, not `os.path`.
- Use f-strings, not `%` or `.format()` (except in logging calls; see Logging).
- Use `enum.StrEnum` for string enums.
- Use `match` statements where they clarify branching over structured data; don't force them.
- Use comprehensions for simple transforms; use loops when logic is non-trivial.
- Use `contextlib` and context managers for resource handling.
- Avoid mutable default arguments.
- Prefer `datetime.now(UTC)`; never use naive datetimes or `datetime.utcnow()`.
- Prefer `collections.abc` types for parameters (`Sequence`, `Mapping`, `Iterable`) and concrete types for return values.

### Things to avoid

- `global` and `nonlocal` except in rare, justified cases.
- `eval`, `exec`, `pickle` on untrusted data, `subprocess` with `shell=True`.
- Bare `except:` and `except Exception: pass`.
- `print()` in library code.
- `assert` for runtime validation (asserts are stripped under `-O`).
- Inheritance hierarchies deeper than two levels. Prefer composition.
- Utility modules named `utils.py` or `helpers.py`. Name modules after what they do.

---

## 6. Naming Conventions

| Entity                | Convention           | Example                         |
|-----------------------|----------------------|---------------------------------|
| Modules / packages    | `snake_case`         | `event_ingestion.py`            |
| Functions / methods   | `snake_case`         | `calculate_total()`             |
| Variables             | `snake_case`         | `retry_count`                   |
| Classes               | `PascalCase`         | `EventProcessor`                |
| Exceptions            | `PascalCase` + `Error` | `ValidationError`             |
| Constants             | `UPPER_SNAKE_CASE`   | `MAX_RETRIES`                   |
| Type variables        | `PascalCase`, short  | `T`, `ModelT`                   |
| Private               | leading underscore   | `_build_query()`                |
| Test functions        | `test_<unit>_<scenario>_<expected>` | `test_charge_card_declined_raises` |
| Pytest fixtures       | noun, `snake_case`   | `db_session`, `event_factory`   |

### Guidelines

- Names should reveal intent. `user_ids` beats `ids`; `is_active` beats `flag`.
- Booleans start with `is_`, `has_`, `can_`, or `should_`.
- Avoid abbreviations except universally known ones (`id`, `url`, `db`, `http`).
- Async functions are **not** suffixed with `_async`. The `async def` is sufficient. If both sync and async versions exist, suffix the sync one with `_sync`.
- Repository methods use verbs: `get`, `list`, `add`, `update`, `remove`. Services use domain verbs: `ingest`, `reconcile`, `publish`.
- Database tables are plural `snake_case` (`events`, `user_accounts`). Columns are singular `snake_case`.
- API paths are plural, kebab-case where multi-word: `/v1/event-batches`.

---

## 7. Type Hints

- **Every** function signature (including tests and private helpers) is fully annotated, including return types.
- mypy runs in strict mode. CI fails on type errors.
- Use modern syntax: `list[str]`, `dict[str, int]`, `X | None`, not `List`, `Dict`, `Optional`.
- Use the `type` statement for aliases: `type UserId = int`. Use `NewType` for IDs that must not be mixed up.
- Use `typing.Protocol` for structural interfaces, especially at layer boundaries.
- Use `TypedDict` or Pydantic models for structured dicts. Avoid `dict[str, Any]` in signatures.
- Use `Self`, `override` (`typing.override`), `Literal`, `Final`, and `ClassVar` where they add clarity.
- Avoid `Any`. When unavoidable, add a comment explaining why.
- `# type: ignore` requires an error code and a justification: `# type: ignore[arg-type]  # upstream stub is wrong, see #123`.
- Do not use `cast` to silence errors you don't understand. Fix the types or narrow with `isinstance`.
- Generic functions and classes use PEP 695 syntax: `def first[T](items: Sequence[T]) -> T: ...`.
- The package ships `py.typed`. Public APIs must be fully typed.

---

## 8. Docstrings and Comments

### Docstrings

- Use **Google style**.
- Required for: all public modules, classes, functions, and methods.
- Optional for: private helpers whose name and signature are self-explanatory, and test functions.
- First line is a one-sentence summary in imperative mood, ending with a period.
- Do not repeat type information in docstrings; the annotations carry it.

```python
async def reconcile_account(account_id: AccountId, *, as_of: datetime) -> Reconciliation:
    """Reconcile ledger entries for an account up to a point in time.

    Compares posted entries against the external statement and records any
    discrepancies. The operation is idempotent for a given ``as_of``.

    Args:
        account_id: The account to reconcile.
        as_of: Upper bound (inclusive) for entries considered. Must be timezone-aware.

    Returns:
        The reconciliation result, including any unmatched entries.

    Raises:
        AccountNotFoundError: If the account does not exist.
        StatementUnavailableError: If the external statement cannot be fetched.
    """
```

### Comments

- Comments explain **why**, not **what**. If a comment restates the code, delete it.
- Keep comments current. A wrong comment is worse than none.
- Use `TODO(username): description (#issue)` format. TODOs without an issue link are not allowed in merged code.
- Don't leave commented-out code.
- Match the comment density of the file you're editing.

---

## 9. Error Handling

### Exception hierarchy

All application exceptions derive from `AcmeError` in `src/acme_service/errors.py`:

```
AcmeError
├── DomainError            # Business rule violations (4xx semantics)
│   ├── ValidationError
│   ├── NotFoundError
│   └── ConflictError
├── InfrastructureError    # Dependencies failing (5xx semantics)
│   ├── DatabaseError
│   └── ExternalServiceError
└── ConfigurationError     # Startup misconfiguration
```

### Rules

- Raise the most specific exception that fits. Add new subclasses rather than overloading messages.
- **Never** catch `Exception` or `BaseException` except at process boundaries (API middleware, Celery task wrapper, `main`). There, log with traceback and convert to a safe response.
- Always chain exceptions: `raise NotFoundError(...) from exc`.
- Don't use exceptions for normal control flow when a simple conditional is clearer.
- Catch narrowly and wrap only the lines that can raise. Keep `try` blocks small.
- Never swallow errors silently. If ignoring is correct, comment why and log at `debug` at least.
- Validate inputs at the boundary (Pydantic) and fail fast with clear messages.
- Error messages are actionable and contain context (IDs, values) but **never secrets or PII**.
- API error responses use RFC 9457 problem details. Handlers map `DomainError` → 4xx and `InfrastructureError` → 5xx in a single central place (`api/app.py`), not per-endpoint.
- Use `try/finally` or context managers for cleanup, not `__del__`.
- Retries: use `tenacity` with exponential backoff and jitter, only for idempotent operations, and always with a bounded attempt count.
- External calls must have explicit timeouts. No unbounded waits.

---

## 10. Logging

- Use the standard library `logging` through structlog configuration in `acme_service/logging.py`.
- Each module: `logger = structlog.get_logger(__name__)`.
- Logs are **structured JSON** in production, human-readable in development.

### Levels

| Level     | Use for                                                      |
|-----------|--------------------------------------------------------------|
| `DEBUG`   | Detailed diagnostics, off in production                      |
| `INFO`    | Significant lifecycle events and business milestones         |
| `WARNING` | Recoverable anomalies, retries, degraded behavior            |
| `ERROR`   | An operation failed and needs attention                      |
| `CRITICAL`| The process cannot continue                                  |

### Rules

- Log key/value fields, not interpolated strings: `logger.info("event_ingested", event_id=event.id, source=event.source)`.
- Event names are short `snake_case` identifiers, stable enough to alert on.
- Use `logger.exception(...)` inside `except` blocks to include the traceback. Don't log and re-raise the same error at every layer; log once, where it's handled.
- **Never log** secrets, tokens, passwords, full card numbers, or personal data. Redact or hash identifiers where needed.
- Bind request-scoped context (`request_id`, `trace_id`, `user_id`) via contextvars middleware; don't pass them manually.
- No `print()`. No logging configuration at import time outside `logging.py`.
- Avoid logging inside tight loops. Aggregate instead.

---

## 11. Testing Strategy

### Pyramid

| Tier        | Location             | Scope                                  | Speed        |
|-------------|----------------------|----------------------------------------|--------------|
| Unit        | `tests/unit/`        | One unit, collaborators faked          | ms           |
| Integration | `tests/integration/` | Real Postgres/Redis, no network egress | seconds      |
| E2E         | `tests/e2e/`         | Full API against running stack         | slowest, few |

Aim for roughly 70% unit, 25% integration, 5% e2e.

### Requirements

- Every bug fix includes a regression test that fails without the fix.
- Every new feature includes tests for the happy path, edge cases, and error paths.
- Minimum coverage is **90% line** and **85% branch** overall; new code should be fully covered. Coverage is a floor, not a goal: don't write meaningless tests to hit a number.
- Tests must be **deterministic**. No reliance on wall-clock time, randomness without a seed, network, or test order.
- Tests must be **independent** and runnable in parallel (`pytest-xdist`).
- No `sleep()` in tests. Use fakes, event waiting, or `freezegun`/`time-machine`.

### Conventions

- Structure tests as Arrange / Act / Assert, separated by blank lines.
- One logical behavior per test; name it `test_<unit>_<scenario>_<expected>`.
- Prefer `pytest.mark.parametrize` over loops inside tests.
- Use fixtures for setup; keep them small and composable. Shared fixtures live in `conftest.py`.
- Use factories (`tests/factories/`) for domain objects, not large JSON blobs.
- Mock at boundaries only (HTTP, clock, third-party SDKs). Don't mock the code under test or internal collaborators when a fake or the real thing is cheap.
- Prefer fakes and in-memory implementations over `unittest.mock` where practical.
- HTTP clients are tested with `respx`/`pytest-httpx`. No real network calls in tests.
- Use `hypothesis` for parsers, validators, and serialization round-trips.
- Async tests use `pytest-asyncio` in auto mode.
- Mark slow or external tests: `@pytest.mark.integration`, `@pytest.mark.slow`.
- Database tests run in a transaction that rolls back, or use a fresh schema per worker.

### Running tests

```bash
make test-fast                       # quick feedback loop
pytest tests/unit/services -k billing  # focused run
pytest -x --lf                       # stop on first failure, rerun last failed
make cov                             # coverage report
```

Run the relevant tests after every change. Run `make check` before declaring work finished.

---

## 12. Continuous Integration

CI runs on GitHub Actions for every pull request and on pushes to `main`.

### Pipeline stages

1. **Setup:** install `uv`, restore cache, `uv sync --frozen`.
2. **Static checks (parallel):**
   - `ruff format --check`
   - `ruff check`
   - `mypy`
   - `import-linter`
3. **Tests:** unit and integration (services via GitHub Actions `services:`), with coverage upload.
4. **Security:** `pip-audit`, `bandit`, secret scanning (`gitleaks`).
5. **Build:** build the Docker image and run a smoke test.
6. **Migrations check:** verify Alembic has a single head and that `upgrade` then `downgrade` works on a clean database.

### Rules

- A PR cannot merge unless all required checks pass.
- Do not disable, skip, or weaken a CI check to get a PR green. Fix the underlying cause.
- Flaky tests are bugs: fix or quarantine them with a linked issue within one business day.
- Never edit workflow files unless the task explicitly requires it; changes to `.github/workflows/` need CODEOWNERS review.
- Keep CI reproducible: pin action versions by SHA and use `uv sync --frozen`.
- Run `make check` locally before pushing so CI is a confirmation, not a discovery.

---

## 13. Git Workflow

### Branching

- `main` is always deployable and protected. No direct pushes.
- Work on short-lived feature branches off `main`.
- Branch naming: `<type>/<short-description>` or `<type>/<ticket>-<short-description>`:
  - `feat/event-batching`
  - `fix/ACME-142-null-timestamp`
  - `chore/bump-ruff`
  - `docs/runbook-redis`
- Keep branches small and rebase on `main` regularly. Prefer **rebase** over merge to update a branch.
- Merges to `main` use **squash merge**, so each PR becomes one commit.

### Rules

- Never force-push to `main`. Force-push to your own feature branch only with `--force-with-lease`.
- Never commit directly to `main`.
- Never rewrite history that others have based work on.
- Don't commit generated files, build artifacts, `.env` files, virtualenvs, or large binaries.
- Do not use `git add -A` blindly; review `git status` and `git diff --staged` first.
- Don't commit unrelated changes together. Separate refactors from behavior changes.
- Before deleting or overwriting files, inspect them first.
- Do not push, open PRs, or take other outward-facing actions unless asked.

---

## 14. Commit Messages

We use **Conventional Commits**.

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

`feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.

### Rules

- Subject: imperative mood, lowercase, no trailing period, **≤ 72 characters**. ("add retry to ingest client", not "Added retries.")
- Scope is the area touched: `api`, `worker`, `db`, `services`, `deps`, etc.
- Body (when needed) explains **what and why**, not how. Wrap at 72 columns.
- Reference issues in the footer: `Closes #123`, `Refs ACME-142`.
- Breaking changes: add `!` after the type/scope and a `BREAKING CHANGE:` footer.
- One logical change per commit. The tree should build and tests should pass at each commit.

### Examples

```
feat(api): add batch ingestion endpoint

Accepts up to 500 events per request and returns per-event status so
callers can retry only failures. Keeps the single-event endpoint
unchanged.

Closes #214
```

```
fix(worker): make reconcile task idempotent

A retry after a partial failure inserted duplicate ledger entries.
Use an upsert keyed on (account_id, statement_line_id).

Refs ACME-142
```

---

## 15. Pull Requests

### Before opening

- [ ] `make check` passes locally.
- [ ] Tests added or updated.
- [ ] Docs, docstrings, and changelog updated if behavior changed.
- [ ] Migrations included and reviewed, if the schema changed.
- [ ] No secrets, debug code, or unrelated changes in the diff.

### Content

- Title follows Conventional Commits (it becomes the squash commit message).
- Description includes: **what** changed, **why**, **how it was tested**, and any **risks or rollout notes**.
- Link the issue or ticket.
- Include screenshots or sample requests/responses for API changes.
- Keep PRs small, ideally under ~400 changed lines excluding lockfiles and generated code. Split larger work into stacked PRs.

### Review

- At least one approval from a CODEOWNER is required.
- Address every review comment: fix it, or reply with reasoning. Don't resolve threads silently.
- Push follow-up commits during review; they are squashed on merge.
- Authors are responsible for their PR until it is merged and verified in production.
- Reviewers check: correctness, tests, readability, security, performance, backward compatibility, and observability.

---

## 16. Security

### Secrets and configuration

- **Never** hardcode or commit secrets, API keys, tokens, or credentials. This includes test fixtures and examples.
- Configuration comes from environment variables, loaded through `acme_service/config.py` (Pydantic Settings). No `os.environ` reads scattered through the code.
- Use `SecretStr` for sensitive settings so they don't leak into logs or reprs.
- `.env` is gitignored. Maintain `.env.example` with placeholder values only.
- If you discover a committed secret, stop, report it, and treat it as compromised. Rotating it is required; deleting it from history is not sufficient.

### Input and output

- Treat all external input as untrusted: request bodies, headers, query parameters, queue messages, files, and third-party API responses.
- Validate with Pydantic at every boundary. Use allow-lists over deny-lists.
- Use SQLAlchemy parameter binding. **Never** build SQL with string formatting or concatenation.
- Never use `pickle`, `yaml.load` (use `safe_load`), `eval`, or `exec` on external data.
- Avoid `subprocess` where possible; when required, pass argument lists, never `shell=True`.
- Validate and normalize file paths to prevent traversal. Use `Path.resolve()` and check containment.
- Set size limits on request bodies, uploads, and batch sizes.

### Authentication and authorization

- Every endpoint is authenticated unless explicitly marked public in code review.
- Authorization is checked in the service layer, not only at the router.
- Never roll your own cryptography. Use `cryptography`, `argon2-cffi` (passwords), and `secrets` for tokens.
- Compare secrets with `hmac.compare_digest`.
- Use `secrets`, never `random`, for anything security-related.

### Data protection

- Do not log PII or secrets. Minimize what is stored.
- TLS for all network traffic. Verify certificates; never set `verify=False`.
- Apply least privilege to database roles and service credentials.

### Dependencies and supply chain

- Add dependencies only when necessary (see Dependencies).
- CI runs `pip-audit` and `bandit`. Fix or document findings; don't suppress them without justification.
- Review the license and maintenance status of any new package.

### Reporting

Security issues are reported privately to the security contact in `SECURITY.md`, never in public issues or PRs.

---

## 17. Performance

- **Measure first.** Don't optimize without a profile or benchmark. Use `cProfile`, `py-spy`, or `pytest-benchmark`.
- Choose correct algorithms and data structures first; micro-optimizations rarely matter.
- Never block the event loop. Offload CPU-bound or blocking calls with `asyncio.to_thread` or the worker.
- Use `asyncio.gather`/`TaskGroup` for independent concurrent I/O, with bounded concurrency (`Semaphore`).
- Database:
  - Avoid N+1 queries; use `selectinload`/`joinedload` deliberately.
  - Select only the columns you need for hot paths.
  - Paginate all list endpoints (cursor-based preferred). Never return unbounded result sets.
  - Add indexes for new query patterns, and verify with `EXPLAIN ANALYZE`.
  - Use bulk operations (`insert().values([...])`) for batch writes.
  - Keep transactions short.
- Reuse connections: shared `httpx.AsyncClient` and pooled DB engines created at startup.
- Use generators and streaming for large datasets instead of loading everything into memory.
- Cache only with a clear invalidation story and TTL. Document what is cached and why.
- Set timeouts on all network calls.
- Performance-sensitive changes include benchmark results in the PR description.

---

## 18. Documentation

- Keep `README.md` accurate: what the project is, how to run it, how to test it.
- Update docs **in the same PR** as the behavior change.
- Significant architectural decisions are recorded as ADRs in `docs/adr/` (`NNNN-title.md`), using the template in `docs/adr/0000-template.md`.
- Operational procedures live in `docs/runbooks/`. Every alert has a linked runbook.
- The API is documented through FastAPI's OpenAPI schema. Give every route a `summary`, `response_model`, and documented error responses.
- Maintain `CHANGELOG.md` in Keep a Changelog format; add an entry under `Unreleased` for every user-visible change.
- Docstrings are the source of truth for code-level documentation (see section 8).
- Don't create new documentation files unless asked or clearly needed.

---

## 19. Dependencies

- Dependencies are declared in `pyproject.toml` and locked in `uv.lock`. Both are committed.
- Add with `uv add <pkg>` (runtime) or `uv add --dev <pkg>` (dev). Don't hand-edit `uv.lock`.
- **Justify new dependencies** in the PR: why the standard library or an existing dependency isn't enough.
- Prefer well-maintained, widely used packages with permissive licenses (MIT, BSD, Apache-2.0). Flag GPL/AGPL for review.
- Pin through the lockfile; use compatible-release ranges in `pyproject.toml` (`>=2.0,<3`).
- Separate groups: runtime, `dev`, `test`, `docs`.
- Remove unused dependencies promptly.
- Dependabot/Renovate opens weekly update PRs. Major upgrades need a dedicated PR with a changelog review.
- Never install packages ad hoc with `pip install` in a way that bypasses the lockfile.
- Do not vendor third-party code.

---

## 20. Database and Migrations

- Schema changes are made only through Alembic migrations. Never alter the schema manually.
- Generate with `make revision m="add event source column"`, then **review and edit** the output. Autogenerate is a starting point.
- Migrations must be **backward compatible** with the previous release (expand/contract pattern): add nullable columns first, backfill, then enforce constraints in a later release.
- Never edit a migration that has been merged. Add a new one.
- Large-table changes use `CREATE INDEX CONCURRENTLY` and batched backfills.
- Each migration has a working `downgrade`, or an explicit comment explaining why it's irreversible.
- Keep one Alembic head. Resolve conflicts by rebasing and regenerating.

---

## 21. Rules the Agent MUST Follow

These are non-negotiable. If a task seems to require breaking one, stop and ask.

### Safety and scope

1. **MUST** read relevant existing code before changing it, and follow its conventions.
2. **MUST** keep changes minimal and focused on the requested task. No drive-by refactors, renames, or reformatting of unrelated code.
3. **MUST NOT** commit, push, merge, open PRs, publish packages, or deploy unless explicitly asked.
4. **MUST NOT** run destructive commands (`rm -rf`, `git reset --hard`, `git clean -fd`, `DROP`, `TRUNCATE`, force-push) without explicit confirmation, and must inspect the target first.
5. **MUST NOT** touch production systems, production data, or real third-party services.
6. **MUST NOT** read, print, copy, or commit secrets, `.env` files, or credentials.
7. **MUST** ask for clarification when requirements are ambiguous or a decision has significant consequences, rather than guessing.

### Code quality

8. **MUST** add or update type hints on every function you write or modify.
9. **MUST** add or update tests for every behavior change and bug fix.
10. **MUST** run `make fmt`, `make lint`, `make typecheck`, and the relevant tests before reporting work as done. Prefer `make check`.
11. **MUST** write Google-style docstrings for new public modules, classes, and functions.
12. **MUST** handle errors with the project's exception hierarchy; never use bare `except` or silently swallow errors.
13. **MUST** use structured logging; never `print()` and never log secrets or PII.
14. **MUST** respect layer boundaries (domain ← repositories ← services ← api/worker).
15. **MUST** use parameterized queries and Pydantic validation at boundaries.
16. **MUST** use timezone-aware datetimes (UTC internally).

### Dependencies and configuration

17. **MUST NOT** add a dependency without stating why and getting approval.
18. **MUST NOT** hand-edit lockfiles or generated files.
19. **MUST** read configuration through `config.py`; never read `os.environ` ad hoc or hardcode environment-specific values.
20. **MUST** create an Alembic migration for any schema change, and never edit an already-merged migration.

### Tests and CI

21. **MUST NOT** delete, skip, `xfail`, or weaken tests to make them pass. Fix the code or explain why the test is wrong.
22. **MUST NOT** disable linters, type checks, or CI steps, or add blanket `# noqa` / `# type: ignore` without a specific code and justification.
23. **MUST NOT** make network calls in unit tests.

### Honest reporting

24. **MUST** report results faithfully. If tests fail, say so and include the relevant output. If a step was skipped or couldn't be run, say that explicitly.
25. **MUST NOT** claim work is complete or verified unless you actually ran the checks and they passed.
26. **MUST** surface uncertainty, assumptions, and follow-up work instead of hiding them.
27. **MUST** mention any unrelated problems noticed (bugs, vulnerabilities, flaky tests) without silently fixing them in the same change.

---

## 22. Recommended Agent Workflow

1. **Understand:** read the task, relevant files, and nearby tests. Check `docs/adr/` for related decisions.
2. **Plan:** for non-trivial work, outline the approach and affected files before editing. Ask if anything is unclear.
3. **Write a failing test** (for bugs and new behavior) when practical.
4. **Implement** the smallest change that satisfies the test and the requirements.
5. **Verify:** run `make fmt && make lint && make typecheck && make test-fast`, then `make check` for broader changes.
6. **Review your own diff:** `git diff`. Remove debug code, stray files, and unrelated edits.
7. **Report:** summarize what changed, why, how it was verified, and anything left open. Be precise about what passed and what wasn't run.

### When stuck

- Don't thrash. If an approach fails twice, step back and reconsider.
- Don't work around a failing check by weakening it. Diagnose the root cause.
- If blocked by missing access, ambiguous requirements, or a conflict with these rules, stop and ask.

---

## 23. Maintaining This File

- Keep `AGENTS.md` accurate. If a rule here is wrong or outdated, propose a fix in a PR.
- Prefer concrete, verifiable rules over vague aspirations.
- Update this file when tooling, layout, or conventions change.
- Subdirectories may contain their own `AGENTS.md` with more specific guidance; the nearest file to the code being edited takes precedence, but must not contradict the MUST rules in section 21.
