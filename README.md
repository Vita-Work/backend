# backend

Backend template for Vita-style services.

## Docs

- [`docs/overview.md`](docs/overview.md)
- [`docs/cv-extraction.md`](docs/cv-extraction.md)
- [`docs/search-setup-architecture.md`](docs/search-setup-architecture.md)
- [`docs/billing-subscriptions.md`](docs/billing-subscriptions.md)
- [`docs/branch-changes.md`](docs/branch-changes.md)

## Environment setup

```bash
cp .env.example .env
```

Required for the CV extraction flow:

- `S3_ENDPOINT_URL`
- `S3_REGION`
- `S3_BUCKET_NAME`
- `S3_ACCESS_KEY_ID`
- `S3_SECRET_ACCESS_KEY`
- `GEMINI_API_KEY`

Required for subscriptions and Paddle checkout:

- `PADDLE_ENVIRONMENT`
- `PADDLE_CLIENT_SIDE_TOKEN`
- `PADDLE_PRODUCT_ID_PRO`
- `PADDLE_PRICE_ID_PRO_MONTHLY`
- `PADDLE_WEBHOOK_SECRET`

## Development

Use Python 3.13 for local development.

Install development tools:

```bash
uv sync --extra dev
uv run pre-commit install
```

Run the project locally:

```bash
uv run uvicorn src.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

Run the ARQ worker:

```bash
uv run arq src.extensions.arq.arq_common.WorkerSettings
```

Billing and monitoring rely on the worker for scheduled monitoring runs.

The frontend expects the backend app-state routes to line up with these user routes:

- `/onboarding`
- `/onboarding/processing`
- `/onboarding/chat`
- `/searching`
- `/results`

If you change user-facing routes on the frontend, update `src/modules/me/frontend_state.py` at the same time so session restore and auth redirects stay correct.

Keep backend route handlers thin:

- route modules should not import private helper functions from sibling route modules
- shared response builders belong in presenter modules
- cross-module orchestration belongs in explicit use-case modules

That keeps HTTP wiring separate from reusable application logic and avoids brittle route-to-route coupling.

Useful health checks:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/db
```

## CV extraction flow

Manual end-to-end test:

```bash
curl -X POST http://127.0.0.1:8000/extraction/cv/run \
  -F "user_id=test-user" \
  -F "file=@/absolute/path/to/resume.pdf"
```

Upload-only test:

```bash
curl -X POST http://127.0.0.1:8000/extraction/cv \
  -F "file=@/absolute/path/to/resume.pdf"
```

More details are in [`docs/cv-extraction.md`](docs/cv-extraction.md).

## Onboarding flow

The main user-facing flow is:

1. `POST /onboarding/users/{user_id}/restart`
2. `POST /extraction/cv/run`
3. `GET /onboarding/users/{user_id}/active`
4. `POST /onboarding/users/{user_id}/respond`

`respond` is used for both clarification answers and final confirmation.

## Billing flow

The subscription architecture is documented in [`docs/billing-subscriptions.md`](docs/billing-subscriptions.md).
