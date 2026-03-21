# CV extraction

## Purpose

The CV extraction flow accepts a candidate CV, stores the original document in S3-compatible object storage, and produces three outputs for the next workflow step:

- `extracted_profile`
- `missing_info`
- `preference_hints`

These outputs are designed for the later clarification step, which asks focused follow-up questions.

## Supported formats

- `pdf`
- `docx`
- `txt`
- `md`

Configured upload limit:

- `CV_UPLOAD_MAX_SIZE_MB=30`

## Flow

1. Client uploads a CV to `POST /extraction/cv` or `POST /extraction/cv/run`.
2. Backend validates extension, content type, size, and basic file signature.
3. Backend stores the original file in S3-compatible storage.
4. Backend chooses extraction strategy:
   - `pdf` -> `model_file`
   - `docx/txt/md` -> `local_text`
5. `POST /extraction/cv/run` persists a workflow run and enqueues background processing in ARQ.
6. The worker starts the unified `search_setup` graph at the `extraction` node.
7. Gemini returns structured output:
   - `extracted_profile`
   - `missing_info`
   - `preference_hints`

## Strategy details

### `model_file`

Used for `pdf`.

- The original file is downloaded from S3 to a temporary local file.
- The file is uploaded to Gemini Files API using the official `google-genai` SDK.
- The extraction prompt requests structured JSON.
- Gemini output is parsed using `response_schema`, so the provider performs the main structured parsing.

### `local_text`

Used for `docx`, `txt`, and `md`.

- The file content is extracted locally into normalized text.
- The normalized text is sent to Gemini.
- Gemini still produces the same structured output contract.

## Main code locations

- `src/modules/extraction/routes.py`
- `src/modules/extraction/use_cases/intake_cv.py`
- `src/modules/extraction/use_cases/queue_cv_extraction.py`
- `src/modules/extraction/use_cases/get_cv_extraction_run.py`
- `src/modules/extraction/parsers/cv.py`
- `src/extensions/s3/s3.py`
- `src/extensions/gemini/gemini.py`
- `src/extensions/arq/jobs/extraction.py`
- `src/workflows/search_setup/nodes/extraction.py`
- `src/workflows/search_setup/graph.py`

## Environment variables

Required:

- `S3_ENDPOINT_URL`
- `S3_REGION`
- `S3_BUCKET_NAME`
- `S3_ACCESS_KEY_ID`
- `S3_SECRET_ACCESS_KEY`
- `GEMINI_API_KEY`

Optional:

- `S3_KEY_PREFIX`
- `S3_CONNECT_TIMEOUT_SECONDS`
- `S3_READ_TIMEOUT_SECONDS`
- `S3_MAX_POOL_CONNECTIONS`
- `CV_UPLOAD_MAX_SIZE_MB`
- `GEMINI_MODEL`
- `GEMINI_API_VERSION`

## Manual local run

Start the server:

```bash
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn src.main:app --reload
```

Run the worker in a second terminal:

```bash
uv run arq src.extensions.arq.arq_common.WorkerSettings
```

Run extraction end-to-end:

```bash
curl -X POST http://127.0.0.1:8000/extraction/cv/run \
  -F "user_id=test-user" \
  -F "file=@/absolute/path/to/resume.pdf"
```

## Notes

- The upload-only endpoint is useful for checking validation and storage without running Gemini.
- The end-to-end endpoint queues work and returns immediately with a workflow run id.
- If S3 credentials are invalid, upload fails before Gemini starts.
- If `GEMINI_API_KEY` is missing or invalid, the workflow fails at extraction time.
