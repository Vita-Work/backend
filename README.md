# backend

Backend template for Vita-style services.

## Docs

- [`docs/overview.md`](/Users/aidin/Projects/vita/backend/docs/overview.md)
- [`docs/cv-extraction.md`](/Users/aidin/Projects/vita/backend/docs/cv-extraction.md)
- [`docs/search-setup-architecture.md`](/Users/aidin/Projects/vita/backend/docs/search-setup-architecture.md)
- [`docs/branch-changes.md`](/Users/aidin/Projects/vita/backend/docs/branch-changes.md)

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
