<div align="center">

# Vita Backend

**Backend for an agentic job-search assistant. Vita turns a CV into a confirmed search plan, runs multi-source job discovery, and keeps workflow state durable across human pauses.**

[![Python 3.13](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agentic%20Workflows-1C3C3C?style=for-the-badge)](https://github.com/langchain-ai/langgraph)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Checkpointing%20%2B%20State-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-ARQ%20Workers-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)

[Overview](#overview) | [Quick Start](#quick-start) | [Pipeline](#pipeline) | [Agentic System](#agentic-system) | [Run Locally](#run-locally) | [Tests](#tests)

</div>

## Overview

Vita is a backend service for CV-driven job search. It receives a resume, extracts career context, asks follow-up questions when the profile is underspecified, verifies the result, builds a search plan, runs job discovery across several sources, deduplicates results, and exposes saved-job/application-support workflows.

This repository contains the backend API, background workers, database models, migrations, provider integrations, and LangGraph workflows behind that flow.

## What It Does

| Capability | Description |
| --- | --- |
| CV intake | Validates PDF/DOCX/TXT/MD uploads, stores originals in S3-compatible storage, and creates workflow runs. |
| Profile extraction | Uses Gemini to produce structured profile text, missing information, and preference hints. |
| Human-in-the-loop onboarding | Pauses the graph for clarification or confirmation and resumes it from the same thread. |
| Search planning | Uses DSPy modules to verify profile quality and produce hard/soft search preferences. |
| Job discovery | Runs a staged LangGraph workflow across job-source adapters, parser tools, dedupe, detail fetch, and unification. |
| Product state | Persists frontend-safe workflow state so refreshes and later sessions recover to the right route. |
| Billing and tracker | Enforces free/pro result gates, handles Paddle webhooks, and stores tracked jobs plus AI application runs. |

## Why

Keyword-based job search is noisy because the user's intent is usually implicit in the CV, not written as a clean query. Vita treats the setup phase as a workflow: extract what is known, ask only for missing constraints, verify that the profile is useful, and only then spend work on search and ranking.

The backend owns that state because the important steps are long-running and interruptible: extraction can fail, search runs in the background, and the user may answer clarification prompts minutes or hours later.

## Quick Start

```bash
cp .env.example .env
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn src.main:app --reload
```

Start the worker in a second terminal:

```bash
uv run arq src.extensions.arq.arq_common.WorkerSettings
```

For the full workflow, configure PostgreSQL, Redis, S3-compatible storage, and Gemini credentials in `.env`.

## Pipeline

```mermaid
flowchart LR
    A["CV upload<br/>PDF, DOCX, TXT, MD"] --> B["Validation<br/>type, size, signature"]
    B --> C["S3-compatible storage"]
    C --> D["Gemini extraction<br/>profile, gaps, preferences"]
    D --> E["LangGraph search_setup"]
    E --> F["Human clarification<br/>interrupt / resume"]
    F --> G["DSPy verification"]
    G --> H["DSPy search plan"]
    H --> I["User confirmation"]
    I --> J["LangGraph search_job"]
    J --> K["Source workers<br/>HH, Habr, GetOnBrd, Indeed, etc."]
    K --> L["Dedupe + detail fetch"]
    L --> M["Gemini embeddings<br/>ranking and unification"]
    M --> N["Results + tracker + billing gates"]
```

The main flow is:

1. **CV intake** validates and stores the original file.
2. **Extraction** uses Gemini to produce `extracted_profile`, `missing_info`, and `preference_hints`.
3. **Onboarding** asks focused clarification questions when the profile is not search-ready.
4. **Verification** checks profile quality before the system spends work on job discovery.
5. **Search planning** turns the verified profile into hard and soft preferences.
6. **Search execution** fans out across job sources, deduplicates listings, fetches details, and builds unified results.
7. **Tracking and application AI** let users save jobs, inspect match gaps, and generate application-support payloads.

## Agentic System

Vita uses LangGraph where the backend needs durable state, conditional routing, parallel fan-out, or human-in-the-loop pauses.

### `search_setup`: CV to confirmed search plan

```mermaid
stateDiagram-v2
    [*] --> extraction
    extraction --> clarification
    clarification --> need_more_context: pending prompt
    need_more_context --> clarification: user answer
    clarification --> verify: enough context
    verify --> clarification: gaps remain
    verify --> search_plan: profile verified
    search_plan --> confirm
    confirm --> clarification: user says no
    confirm --> [*]: user confirms
```

Agentic behavior in this graph:

- conditional routing decides whether to ask the user, verify the profile, build a plan, or loop back;
- `interrupt` / `resume` handles human answers without keeping an HTTP request open;
- PostgreSQL checkpointing keeps the graph thread durable;
- verification and confirmation can route the workflow back into clarification instead of forcing a linear flow.

Key files:

- [`src/workflows/search_setup/graph.py`](src/workflows/search_setup/graph.py)
- [`src/workflows/search_setup/state.py`](src/workflows/search_setup/state.py)
- [`src/workflows/search_setup/runtime.py`](src/workflows/search_setup/runtime.py)
- [`docs/search-setup-architecture.md`](docs/search-setup-architecture.md)

### `search_job`: confirmed plan to ranked jobs

```mermaid
flowchart TD
    A["plan_search_execution"] --> B["dispatch_source_workers"]
    B --> C["source_worker per site"]
    C --> D["listing_dedupe"]
    D --> E["dispatch_detail_fetch"]
    E --> F["detail_fetch per site"]
    F --> G["detail_dedupe"]
    G --> H["dispatch_unification"]
    H --> I["unify_jobs_batch"]
    I --> J["finalize_search_results"]
```

Agentic behavior in this graph:

- `Send` fans out work across selected sources and detail-fetch batches;
- the graph joins results into listing dedupe, detail dedupe, and unification stages;
- expensive AI work is reserved for planning, embeddings, ranking, and explanation;
- persisted progress events make a long search run visible to the frontend and easier to debug.

Key files:

- [`src/workflows/search_job/graph.py`](src/workflows/search_job/graph.py)
- [`src/workflows/search_job/state.py`](src/workflows/search_job/state.py)
- [`src/workflows/search_job/nodes/`](src/workflows/search_job/nodes)
- [`docs/search-job-mvp.md`](docs/search-job-mvp.md)

### `job_application`: tracked job to application packet

The application workflow takes a tracked job plus the user's profile context and can produce match-gap analysis, a tailoring plan, a tailored resume payload, and an application packet.

Key files:

- [`src/workflows/job_application/graph.py`](src/workflows/job_application/graph.py)
- [`src/modules/job_ai/`](src/modules/job_ai)
- [`src/modules/job_tracker/`](src/modules/job_tracker)

## Architecture

```mermaid
flowchart TB
    Client["Frontend / API clients"] --> API["FastAPI app"]
    API --> Modules["Product modules<br/>auth, onboarding, extraction, search, tracker, billing"]
    API --> DB[("PostgreSQL<br/>users, sessions, runs, checkpoints")]
    API --> Redis[("Redis")]
    Redis --> Worker["ARQ worker"]
    Worker --> Graphs["LangGraph workflows"]
    Graphs --> Gemini["Gemini<br/>extraction, embeddings, generation"]
    Graphs --> DSPy["DSPy<br/>verification, planning"]
    Worker --> Sources["Job sources<br/>scrapers and parsers"]
    API --> S3["S3-compatible object storage"]
    API --> Paddle["Paddle billing"]
    API --> Resend["Resend email OTP"]
```

| Layer | Responsibility | Notable paths |
| --- | --- | --- |
| API | FastAPI app, CORS, health checks, route registration | [`src/main.py`](src/main.py) |
| Modules | Product boundaries and use cases | [`src/modules/`](src/modules) |
| Workflows | LangGraph orchestration and workflow state | [`src/workflows/`](src/workflows) |
| Extensions | Provider and infrastructure clients | [`src/extensions/`](src/extensions) |
| Services | Job parser adapters and search tools | [`src/services/`](src/services) |
| Data | SQLAlchemy models, engine, migrations | [`src/db/`](src/db), [`alembic/`](alembic) |
| Docs | Deeper architecture notes and endpoint reference | [`docs/`](docs), [`endpoints.md`](endpoints.md) |

## Technology

| Area | Stack |
| --- | --- |
| API | Python 3.13, FastAPI, Uvicorn, Pydantic Settings |
| Persistence | PostgreSQL, SQLAlchemy, Alembic |
| Background work | Redis, ARQ workers, ARQ cron |
| Agent orchestration | LangGraph, LangGraph Postgres checkpointing, LangChain messages |
| AI providers | Gemini via `google-genai`, Gemini embeddings, DSPy ChainOfThought modules |
| Storage | S3-compatible object storage via aioboto3 |
| Auth and email | Cookie sessions, Argon2 password hashing, Resend OTP email |
| Billing | Paddle checkout, signed webhooks, server-side entitlements |
| Scraping and parsing | Playwright, Scrapling, HTTPX, lxml, source-specific parser adapters |
| Quality | pytest, Ruff, pre-commit |

## Run Locally

### Prerequisites

- Python `3.13`
- [`uv`](https://docs.astral.sh/uv/)
- PostgreSQL
- Redis
- S3-compatible bucket credentials
- Gemini API key

Optional for full product flows:

- Paddle sandbox credentials for billing
- Resend API key for email OTP
- Playwright browsers for job-source scraping

### 1. Configure environment

```bash
cp .env.example .env
```

Minimum variables for the core CV-to-search workflow:

```bash
CONNECTION_STRING=postgresql+asyncpg://user:password@localhost:5432/vita
REDIS_HOST=localhost
REDIS_PORT=6379
S3_ENDPOINT_URL=
S3_REGION=auto
S3_BUCKET_NAME=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
GEMINI_API_KEY=
DSPY_MODEL=
AUTH_SECRET_KEY=change-me
```

The full list lives in [`.env.example`](.env.example).

### 2. Install dependencies

```bash
uv sync --extra dev
```

### 3. Run migrations

```bash
uv run alembic upgrade head
```

### 4. Start the API

```bash
uv run uvicorn src.main:app --reload
```

The API will be available at:

- `http://127.0.0.1:8000`
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/health/db`

### 5. Start the worker

```bash
uv run arq src.extensions.arq.arq_common.WorkerSettings
```

The worker processes CV extraction, search-job workflows, tracked-job AI runs, and billing monitoring jobs.

## API Flow

The main happy path is:

```bash
# 1. Create or identify a user
POST /users

# 2. Upload a CV and queue extraction
POST /extraction/cv/run

# 3. Poll the active onboarding state
GET /onboarding/users/{user_id}/active

# 4. Answer clarification or confirmation prompts
POST /onboarding/users/{user_id}/respond

# 5. Poll search results after confirmation
GET /me/search-jobs/runs/{workflow_run_id}
```

Useful docs:

- [`endpoints.md`](endpoints.md)
- [`docs/cv-extraction.md`](docs/cv-extraction.md)
- [`docs/search-setup-architecture.md`](docs/search-setup-architecture.md)
- [`docs/search-job-mvp.md`](docs/search-job-mvp.md)
- [`docs/billing-subscriptions.md`](docs/billing-subscriptions.md)

## Tests

Run the full test suite:

```bash
uv run pytest
```

Run linting:

```bash
uv run ruff check .
uv run ruff format --check .
```

Current coverage areas include:

| Area | Examples |
| --- | --- |
| App and config | health routes, CORS, environment parsing |
| Auth | email OTP request behavior |
| Extraction | CV text parsing, Gemini service behavior, queueing, worker persistence |
| LangGraph workflows | search setup graph, clarification graph, extraction node, verify node, search job graph |
| Onboarding | restart, response routing, search queue handoff |
| Search jobs | context building, queueing, result response shaping, parsers and tools |
| Billing | Paddle signature and service behavior |
| Tracker | saved-job service, CSV export, AI run surfaces |

Representative files:

- [`tests/workflows/test_search_setup_graph.py`](tests/workflows/test_search_setup_graph.py)
- [`tests/workflows/test_search_job_graph.py`](tests/workflows/test_search_job_graph.py)
- [`tests/extensions/arq/jobs/test_extraction.py`](tests/extensions/arq/jobs/test_extraction.py)
- [`tests/modules/search_jobs/use_cases/test_queue_search_job_workflow.py`](tests/modules/search_jobs/use_cases/test_queue_search_job_workflow.py)
- [`tests/modules/billing/test_paddle.py`](tests/modules/billing/test_paddle.py)

## Project Status

Vita Backend is an active research/product prototype, not a packaged library. The strongest implemented surfaces are:

- durable CV extraction and onboarding state;
- LangGraph-based clarification, verification, planning, and confirmation;
- background job search with staged source fan-out and dedupe;
- authenticated user state restoration through `/me/app-state`;
- job tracking, billing entitlements, and application-support workflows.

Known areas that are still evolving:

- geo-aware source selection and ranking;
- broader multilingual unattended E2E coverage;
- production hardening for optional scraping dependencies;
- public deployment documentation and security policy.

## Contributors

| Contributor | GitHub |
| --- | --- |
| Aidin Khan | [aidin1324](https://github.com/aidin1324) |
| Nikita Nosov | [Nik1t7n](https://github.com/Nik1t7n) |

## Repository

```text
backend/
|-- src/
|   |-- modules/       # product use cases and API route modules
|   |-- workflows/     # LangGraph graphs and workflow state
|   |-- extensions/    # Gemini, DSPy, S3, ARQ, Resend integrations
|   |-- services/      # job parsers and source tools
|   `-- db/            # SQLAlchemy engine, base models, helpers
|-- alembic/           # database migrations
|-- docs/              # architecture and feature notes
|-- tests/             # unit and workflow tests
|-- endpoints.md       # API endpoint reference
`-- pyproject.toml     # dependencies and tooling
```
