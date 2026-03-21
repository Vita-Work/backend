# Branch Changes

Branch: `feat/search-set-up`

This document summarizes the main backend changes introduced on this branch.

## 1. Added base backend infrastructure

- added Alembic setup
- added user model, repository, schemas, routes, and use cases
- added shared database helpers and DB URL utilities
- improved application startup and health-check wiring

Main files:

- `alembic.ini`
- `alembic/`
- `src/modules/users/`
- `src/db/url.py`

## 2. Added S3-backed CV intake

- added async S3 integration
- added upload validation for size, type, and signature
- added storage of the original CV in S3-compatible object storage
- added support for `pdf`, `docx`, `txt`, and `md`

Main files:

- `src/extensions/s3/s3.py`
- `src/modules/extraction/use_cases/intake_cv.py`
- `src/modules/extraction/parsers/cv.py`

## 3. Added Gemini-based CV extraction

- added provider integration with official `google-genai`
- added `Files API` path for PDF
- added text-based path for locally parsed formats
- added structured extraction output:
  - `extracted_profile`
  - `missing_info`
  - `preference_hints`

Main files:

- `src/extensions/gemini/gemini.py`
- `src/workflows/search_setup/nodes/extraction.py`

## 4. Moved extraction out of the request path

- replaced synchronous-in-request extraction execution
- added `extraction_workflow_runs`
- added ARQ queueing and worker processing
- added workflow-run polling endpoint

Main files:

- `src/modules/extraction/models.py`
- `src/modules/extraction/repository.py`
- `src/modules/extraction/use_cases/queue_cv_extraction.py`
- `src/modules/extraction/use_cases/get_cv_extraction_run.py`
- `src/extensions/arq/jobs/extraction.py`

## 5. Added onboarding persistence

- introduced `onboarding_sessions`
- added one active onboarding session per user
- persisted human-in-the-loop state and planning outputs
- added restart and active-session endpoints

Main files:

- `src/modules/onboarding/models.py`
- `src/modules/onboarding/repository.py`
- `src/modules/onboarding/routes.py`
- `src/modules/onboarding/use_cases/`

## 6. Unified the workflow into one LangGraph

The graph is now a single business workflow instead of split graphs.

Flow:

1. extraction
2. clarification
3. verify
4. search_plan
5. confirm

Corrective branches:

- `verify=no` -> one corrective clarification cycle
- `confirm=no` -> one corrective clarification cycle, then re-verify and re-plan

Main files:

- `src/workflows/search_setup/graph.py`
- `src/workflows/search_setup/runtime.py`
- `src/workflows/search_setup/state.py`
- `src/workflows/search_setup/nodes/`

## 7. Added DSPy reasoning nodes

- added DSPy integration
- added `VerifyProfileSignature`
- added `SearchPlanSignature`
- used `ChainOfThought` for verification and planning

Main files:

- `src/extensions/dspy/dspy.py`
- `src/workflows/search_setup/signatures/verify_profile.py`
- `src/workflows/search_setup/signatures/search_plan.py`
- `src/workflows/search_setup/nodes/verify.py`
- `src/workflows/search_setup/nodes/search_plan.py`

## 8. Added final confirmation loop

- added human-in-the-loop confirmation via graph interrupt/resume
- added corrective planning after `confirm=no`
- persisted final hard and soft preferences

Main files:

- `src/workflows/search_setup/nodes/confirm.py`
- `src/modules/onboarding/use_cases/advance_onboarding_flow.py`

## 9. Fixed branch-level architectural issues

Important fixes made during implementation:

- `Gemini` clarification input now includes verification summary
- extraction node can be safely skipped when `extracted_profile` already exists
- worker and onboarding use cases now tolerate monkeypatched sync graph factories in tests
- corrective clarification rounds are counted per cycle, not by total turn count
- onboarding restart now supersedes the previous active session before creating a new draft, which avoids partial-unique-index violations

## 10. Added tests

Added coverage for:

- user creation and duplicate-email conflict mapping
- Gemini parsing behavior
- ARQ extraction worker persistence
- extraction queueing
- onboarding restart and flow advancement
- extraction node
- verify node
- unified graph behavior, including confirmation correction flow

Main test areas:

- `tests/extensions/`
- `tests/modules/`
- `tests/workflows/`

## Result

This branch turns the backend from a template into a working search-setup service with:

- CV upload and storage
- provider-based extraction
- background processing
- persistent onboarding state
- human-in-the-loop clarification and confirmation
- DSPy-based verification and planning
- one unified orchestration graph
