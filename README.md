# backend

Backend template for Vita-style services.

## Development

Use Python 3.13 for local development.

Install development tools:

```bash
uv sync --extra dev
uv run pre-commit install
```

Run the project:

```bash
uv run uvicorn src.main:app --reload
```

Run the ARQ worker:

```bash
uv run arq src.extensions.arq.arq_common.WorkerSettings
```

Environment setup:

```bash
cp .env.example .env
```
