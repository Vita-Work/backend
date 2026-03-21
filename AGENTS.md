# Backend Agent Guide

This file defines how coding agents should work in this backend repository.
Apply the same rules to implementation, refactors, debugging, and reviews.

## 1. Operating Principles

### Stay accurate
- Do not invent behavior, APIs, settings, or DB schema details.
- If ambiguity changes business logic, public API, schema, or migration shape, stop and ask.
- If ambiguity is minor, state the assumption briefly and proceed with the safest minimal option.

### Stay in scope
- Change only what is required for the current task.
- Do not rewrite nearby code "for cleanliness" unless it directly blocks the task.
- If you notice a separate issue, mention it explicitly instead of silently fixing unrelated areas.

### Prefer the simplest working solution
- Start with the smallest change that solves the problem.
- Do not add abstractions, services, base classes, or helpers without repeated need.
- Prefer explicit code over clever code.

### Leave the codebase cleaner
- Remove dead code, stale imports, and temporary debug leftovers created during the task.
- Do not leave commented-out code behind.
- Update docstrings, examples, and related docs when behavior changes.

## 2. Expected Work Style

### Before coding
- Read the relevant files first.
- Identify which layer owns the change: route, use-case, repository, service, middleware, or config.
- For medium or large changes, outline a short plan before editing.

### While coding
- Preserve existing user changes.
- Keep diffs focused and easy to review.
- Prefer typed, explicit function signatures over passing loosely structured dicts through many layers.

### After coding
- Run the smallest meaningful verification for the touched area.
- Report clearly what was verified and what was not run.
- If something could not be verified locally, say so directly.

## 3. Architecture Rules

The backend uses a modular FastAPI structure with shared infrastructure in `src/`.

### Layer responsibilities
- `src/main.py`: app assembly, middleware, router registration, lifecycle wiring.
- `src/config.py`: all settings access and environment-driven configuration.
- `src/logger.py`: logging setup and shared logging helpers.
- `src/db/`: engine, sessions, base classes, shared DB primitives.
- `src/modules/<feature>/routes.py`: thin HTTP layer only.
- `src/modules/<feature>/use_cases/`: business orchestration and domain decisions.
- `src/modules/<feature>/repository.py`: database access only.
- `src/services/`: external providers and third-party integrations.
- `src/extensions/`: framework or infrastructure adapters like ARQ and Redis.

### Boundaries
- Routes validate input, call use-cases, and map results to schemas.
- Use-cases own business flow, permissions, orchestration, and transaction intent.
- Repositories do not contain HTTP concerns or business policy.
- Services do not read FastAPI request objects directly.
- Do not put business logic in models, route handlers, or middleware.

## 4. Coding Standards

### General style
- Use Python type hints consistently.
- Keep public docstrings in English.
- Comments should explain why, constraints, or non-obvious tradeoffs.
- Prefer small functions with explicit names.
- Prefer keyword arguments when a function takes multiple IDs or similar primitives.

### Function design
- Pass important identifiers explicitly, for example `user_id`, `project_id`, `job_id`.
- Avoid vague names like `id`, `data`, `item`, or `payload` when a more specific name exists.
- Avoid boolean flag explosions. If behavior branches heavily, split the function.
- Return domain-relevant values, not half-structured tuples that force callers to guess meanings.

### Async discipline
- Keep database and I/O paths async-first.
- Do not introduce blocking network or disk work into request handlers or async jobs.
- If a task must run in background, make that boundary explicit.

## 5. Logging And Observability

Use the shared logger from `src.logger`. Logging in this project is structured and context-aware.

### Base rules
- Always create loggers via `from src.logger import get_logger`.
- Define the logger once per module, for example `logger = get_logger("users.sync")`.
- Event names must be short, stable, and `snake_case`.
- Put context in structured fields, not inside formatted message strings.

Good:

```python
logger.info(
    "user_sync_started",
    user_id=user_id,
    provider="telegram",
)
```

Bad:

```python
logger.info(f"Started sync for user {user_id} in telegram")
```

### IDs and context
- Pass IDs as explicit log fields: `request_id`, `user_id`, `job_id`, `project_id`, `task_id`.
- If several IDs are present, use precise names instead of a generic `id`.
- If the same context is needed for several logs in one scope, bind it once:

```python
log = logger.bind(user_id=user_id, project_id=project_id)
log.info("project_sync_started")
log.info("project_sync_finished", imported_count=items_count)
```

- Do not bind large mutable objects, ORM instances, request bodies, or secrets.

### Request and job correlation
- HTTP requests already get `request_id` from `RequestContextMiddleware`.
- When calling external services from a request flow, propagate the current request id when useful via `get_current_request_id()`.
- Background jobs should preserve correlation context. When enqueueing ARQ jobs, pass `_parent_request_id` and `_user_id` if they exist.
- Inside ARQ jobs, rely on the middleware binding instead of manually rebuilding the context each time.

### What to log
- Log meaningful lifecycle points for long-running or failure-prone work:
- request start / finish / failure
- external API start / finish / failure
- background job start / finish / failure
- important state transitions

- Include quantitative fields when useful: `duration_seconds`, `status_code`, `items_count`, `retry_attempt`.
- Use `exc_info=True` for unexpected exceptions.
- Avoid duplicate error logs in every layer. Log once where the error becomes actionable or where context is richest.

### Sensitive data
- Never log passwords, tokens, secrets, raw authorization headers, or full sensitive payloads.
- Avoid logging personal data unless it is operationally necessary and approved by product requirements.
- Prefer IDs and safe metadata over raw content.

## 6. Error Handling

- Fail fast on invalid input.
- Raise domain-specific exceptions from use-cases and repositories where appropriate.
- Keep error responses consistent and mapped centrally.
- Do not swallow exceptions silently.
- If catching an exception only to log it, either re-raise it or convert it into a well-defined domain error.

## 7. Database And Migrations

- Use async SQLAlchemy consistently.
- Register every model in `src/db/all_models.py` for Alembic autogeneration.
- Use `uv run alembic revision --autogenerate` and review the migration before applying it.
- Keep migrations manual; do not add auto-run migration hooks.
- Repository methods should encapsulate query logic so it is not duplicated across use-cases.

## 8. Testing And Verification

- Verify the touched behavior, not just syntax.
- Prefer the smallest meaningful test scope first: unit test, then integration path, then endpoint flow.
- For API work, validate with real HTTP requests when practical.
- Check logs and persisted state when the change affects jobs, external sync, or DB writes.
- Fix discovered bugs before moving on to unrelated follow-up work.

## 9. Git And Delivery

- Use Conventional Commits.
- Keep one logical change per commit when possible.
- Run `pre-commit run --all-files` before committing.
- Do not commit failing lint, formatting, or test states.
- Default development branch is `dev` unless the user explicitly asks otherwise.

## 10. Review Checklist

Before considering the task done, confirm:
- the change lives in the correct layer
- logging uses structured fields instead of string interpolation
- IDs are passed with explicit names
- no secrets are logged
- dead code and unused imports are removed
- verification was run or the gap was clearly reported
