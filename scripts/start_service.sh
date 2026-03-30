#!/usr/bin/env bash

set -euo pipefail

role="${VITA_RUNTIME_ROLE:-api}"

case "$role" in
  api)
    uv run alembic upgrade head
    exec uv run uvicorn src.main:app \
      --host 0.0.0.0 \
      --port "${PORT:-8000}" \
      --proxy-headers \
      --forwarded-allow-ips="*"
    ;;
  worker)
    exec uv run arq src.extensions.arq.arq_common.WorkerSettings
    ;;
  *)
    echo "Unsupported VITA_RUNTIME_ROLE: $role" >&2
    exit 1
    ;;
esac
