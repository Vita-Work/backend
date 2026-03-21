## Critical Rules

### 1. NO assumptions
- **Always ask** if something is unclear
- State your assumptions explicitly before starting and wait for confirmation
- If multiple interpretations exist — list them and clarify

### 2. Surface issues
- If you spot inconsistencies in code or requirements — **report them**, don't ignore
- Present tradeoffs explicitly: "Option A: [pros/cons], Option B: [pros/cons]"
- **Push back** if request seems wrong, overcomplicated, or unnecessary

### 3. Simplicity > Complexity
- Propose the **minimal solution** first
- No extra abstractions, classes, layers without explicit need
- Ask yourself: "Can this be 10x simpler?" — if yes, do it simpler

### 4. Don't touch what's outside the task scope
- **Forbidden** to change/remove comments, code, formatting unrelated to current task
- If you see "bad" code nearby — you may mention it, but **don't modify** without request

### 5. Clean up after yourself
- After refactoring, remove dead code, unused imports
- Don't leave commented-out old code

### 6. Plan before code
- For tasks > 50 lines, describe plan in 3-5 bullet points first
- Wait for "ok" before implementation

## Response format

- Brief, to the point
- Code without redundant comments like `// increment counter`
- If uncertain — say so directly, don't make things up

## Comments & Docstrings

### Comments
- Comments must explain **why**, constraints, tradeoffs, or non-obvious behavior, not restate the code.
- Prefer fixing unclear code over adding explanatory comments for obvious logic.
- Use only a small set of explicit comment markers:
  - `# TODO:` planned improvement that is intentionally postponed.
  - `# FIXME:` known bug, broken edge case, or incorrect temporary behavior.
  - `# NOTE:` important context, invariant, or caveat that future readers must know.
  - `# HACK:` intentional workaround for a framework, library, or legacy limitation.
  - `# PERF:` performance-sensitive area where changes require extra care.
- Every tagged comment must be actionable and specific. Bad: `# TODO: improve this`. Good: `# TODO: replace in-memory cache with Redis before enabling multi-instance deployment`.
- Do not leave commented-out code in the repository.

### Docstrings
- Write docstrings in English for public modules, classes, functions, and methods that define behavior or contracts.
- Skip docstrings for trivial private helpers unless behavior is non-obvious.
- Start with a short imperative summary line.
- Add details only when they provide real value: side effects, transaction boundaries, invariants, raised exceptions, or integration expectations.
- For non-trivial functions use a consistent section style with `Args:`, `Returns:`, and `Raises:` when applicable.
- Keep docstrings implementation-light: describe behavior and contract, not line-by-line internals.
- Update docstrings together with code changes; stale docstrings are treated as bugs.


---

# Backend Core Principles

This document outlines the architectural standards and core principles for the backend implementation. These guidelines ensure consistency, scalability, and maintainability across all features.

## 1. Project Organization
The system follows a **Modular Feature-Based Architecture**. Each business domain is isolated to ensure high cohesion and low coupling.

*   **`src/` root infrastructure**: Shared application infrastructure. At the current stage this includes configuration and logging modules such as `src/config.py` and `src/logger.py`. If shared infrastructure grows, it may be moved into `src/core/`.
*   **`src/db/`**: Persistence layer. Configures the asynchronous database engine, session management, and base mixins (e.g., UUID primary keys, timestamps).
*   **`src/modules/<feature>/`**: Domain-specific capsules. Every module must follow a fixed structure:
    *   `models.py`: SQLAlchemy database models.
    *   `schemas.py`: Pydantic request/response contracts.
    *   `use_cases/`: Business logic layer. Each Python file encapsulates one high-level feature or processing pipeline. Examples:
        *   `notification_dispatch.py` — orchestrates sending notifications across channels (email, push, Telegram)
        *   `data_ingestion.py` — handles bulk import, validation, and normalization of incoming data
        *   `report_generation.py` — aggregates data and produces structured reports
        *   `access_control.py` — enforces permission checks and role-based logic
        *   `sync_pipeline.py` — manages incremental sync with external services
    *   `repository.py`: Data access layer. Centralizes all CRUD and query operations. Use-cases import from here instead of duplicating DB logic. If multiple use-cases share the same create/update/delete pattern — it belongs here, not inline.
    *   `routes.py`: API endpoint definitions (thin layer).
    *   `exceptions.py`: Errors specific to this domain.
*   **`src/services/`**: External integrations. High-level adapters for third-party systems (e.g., Telegram bots, hashing services).
*   **`src/extensions/`**: Lightweight integrations for external tools like Redis or Task Queues.

## 2. Configuration Management
*   **Type Safety**: Driven by `pydantic-settings`. All environment variables are validated at startup.
*   **Environment Specificity**: Configuration is loaded from `.env` files (e.g., `.env.staging`, `.env.production`).
*   **Centralization**: The application only interacts with settings through `src.config`.

## 3. Database & Migrations (Alembic)
*   **Async-First**: All database interactions use asynchronous SQLAlchemy.
*   **Alembic Integration**:
    *   **Model Registry**: `src/db/all_models.py` MUST import every model in the project. Alembic uses this central registry for schema autogeneration.
    *   **Async Migrations**: `alembic/env.py` is configured to execute migrations via the async engine, ensuring compatibility with the main application runtime.
    *   **Execution Rule**: Use `uv run alembic <command>` for migration workflows. Prefer `revision --autogenerate`, review, then `upgrade head`.
    *   **Sandbox Rule**: If DB access is required, run migration commands outside sandbox only after explicit user approval.
*   **Schema Consistency**: All models inherit from a common `Base` and use standard mixins for auditing and identification.

## 4. Lifecycle & Entrypoint
*   **Entrypoint**: `src/main.py` is the definitive entrypoint where the FastAPI instance is initialized.
*   **Lifespan Management**: Asynchronous resources (connection pools, bot clients) are initialized and terminated using the FastAPI `lifespan` context manager to ensure graceful shutdowns.
*   **Decoupled Routing**: Routers are defined within modules and registered in `main.py` using a consistent versioning prefix (e.g., `/api/v1`).

## 5. Error Handling
*   **Standardized Responses**: A hierarchy of exceptions starting from a base `AppException`.
*   **Exception Mapping**: Global handlers in `main.py` transform exceptions into consistent JSON responses. This prevents internal stack traces from leaking to clients while providing actionable feedback.

## 6. Engineering Standards
*   **Dependency Management**: `uv` is the standard for fast and reproducible environment setup.
    *   **Running the API**: Use `uv run uvicorn src.main:app --reload` for local development.
    *   **Running Background Jobs**: Use `uv run arq src.extensions.arq.arq_common.WorkerSettings` when the project needs ARQ workers.
    *   **Adding Dependencies**: Use `uv add <package>` to install new libraries and automatically update `pyproject.toml`.
    *   **Principle**: Never use `pip` directly. Using `uv run` ensures that the lockfile is respected and the environment is consistent.
*   **Diagnostics**: Centralized logging via `structlog` provides structured, readable output across all application layers.
*   **Separation of Concerns**: Routes perform validation, use-cases implement logic, repositories handle data access, and models define state. No business logic should reside in the routing layer.

## 7. Basic Testing Strategy
*   **Iterative Endpoint Validation**:
    *   **Process**: Sequentially test endpoints against the running local server. **One request at a time.**
    *   **Cycle**: Request -> Analyze Response -> Fix Bug (if any) -> Retry -> Next Endpoint.
    *   **Scope**: Covers functional correctness, error handling (4xx/5xx), and data integrity.
    *   **Tools**: Use `curl` or HTTP clients for verification, ensuring the application state evolves correctly.

## 8. Git Standards
*   **Conventional Commits**: All commit messages MUST follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification.
    *   Format: `<type>[optional scope]: <description>`
    *   Types: `feat:` (new feature), `fix:` (bug fix), `docs:`, `style:`, `refactor:`, `perf:`, `test:`, `chore:`, `build:`, `ci:`.
    *   Example: `feat(auth): add JWT refresh token support`
*   **Before Commit Checklist**:
    *   Run `pre-commit run --all-files` before creating a commit.
    *   If hooks modify files, review the changes, `git add` them again, and rerun the commit.
    *   Do not commit with failing hooks, lint errors, or formatting drift.
    *   Keep the commit scoped to one logical change-set when possible.
*   **Commit Message Rule**:
    *   Subject line must be short, imperative, and specific.
    *   Avoid vague messages such as `update`, `fix stuff`, `changes`, or `init architecture`.
    *   Prefer messages like `chore(template): add FastAPI and ARQ project scaffold`.
*   **Branching Strategy**:
    *   **Default Branch**: All development work and commits MUST be directed to the `dev` branch by default.
    *   **Main Branch**: Commits to the `main` branch are only permitted if explicitly requested by the USER or for production releases.
    *   **Workflow**: Always check the current branch before committing. If on `main` without specific instructions, switch to `dev`.

## 9. Delivery Discipline (Additional)
*   **Commit Granularity**:
    *   Create a separate commit after each logical change-set (not one huge mixed commit).
    *   If the user explicitly requests push after each change-set, push immediately after each commit.
*   **Bug Handling Rule**:
    *   If any bug is discovered during implementation or testing, fix it immediately before moving to the next test or feature.
*   **Verification Rule**:
    *   Validate features with real API calls (`curl`/HTTP) and confirm critical results with direct DB checks.
*   **Migration Safety**:
    *   Database migrations are manual-only (`uv run alembic ...`).
    *   Do not add automatic pre-deploy migration hooks.
*   **Incremental Sync Integrity**:
    *   For connector sync flows, process only new data after watermark unless user explicitly requests a resync mode.
*   **Secrets Hygiene**:
    *   Keep secrets only in environment files/secrets manager.
    *   Never commit secrets; keep `.env.example` sanitized and `gitignore` strict.
*   **Agent-Native Parity**:
    *   Any important user capability should have agent parity where applicable.
    *   Agent operations must be auditable.
