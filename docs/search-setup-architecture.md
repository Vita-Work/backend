# Search Setup Architecture

## Goal

The search-setup workflow turns an uploaded CV into a confirmed search plan that can later drive job discovery.

The final business flow is:

1. Upload CV
2. Extract candidate context
3. Ask clarification questions
4. Verify the profile quality
5. Build a search plan
6. Ask the user for final confirmation

## Layers

### `src/extensions/`

External integrations and infrastructure:

- `s3/` stores original CV files
- `gemini/` runs CV extraction and clarification decisions
- `dspy/` runs profile verification and search planning
- `arq/` runs background jobs with Redis

### `src/modules/extraction/`

API and orchestration for CV intake:

- validates uploaded files
- stores files in S3
- creates `extraction_workflow_runs`
- queues background processing in ARQ

### `src/modules/onboarding/`

Persistent product state for the user-facing flow:

- stores the active onboarding session
- stores extracted profile data
- stores clarification history
- stores pending human prompts
- stores final planning outputs

### `src/workflows/search_setup/`

Unified `LangGraph` workflow for onboarding.

Main files:

- `graph.py`
- `runtime.py`
- `state.py`
- `nodes/extraction.py`
- `nodes/clarification.py`
- `nodes/verify.py`
- `nodes/search_plan.py`
- `nodes/confirm.py`

## Unified graph

The graph is a single workflow:

```text
START
-> extraction
-> clarification
-> need_more_context? -> wait for user
-> verify
-> if verify needs correction -> clarification(max_rounds=1)
-> search_plan
-> confirm
-> if confirm=no -> clarification(max_rounds=1)
-> verify
-> search_plan
-> confirm
-> END
```

Important implementation detail:

- clarification loops are controlled per cycle, not by total chat length
- this is why the state contains `clarification_cycle_start_index`

Without that field, corrective clarification after `confirm=no` would incorrectly skip the extra question when the user already had earlier clarification turns.

## Persistence model

### `extraction_workflow_runs`

Tracks background extraction jobs:

- upload metadata
- storage key and URI
- workflow status
- extraction result snapshot

### `onboarding_sessions`

Tracks the user-facing onboarding state:

- `status`
- `current_step`
- `extracted_profile`
- `missing_info`
- `preference_hints`
- `clarification_turns`
- `pending_user_prompt`
- `pending_user_prompt_type`
- `verification_score`
- `verification_summary`
- `search_strategy_summary`
- `hard_preferences`
- `soft_preferences`

Only one active onboarding session is allowed per user.

## API flow

### `POST /onboarding/users/{user_id}/restart`

Creates a fresh onboarding draft and supersedes the previous active session.

### `POST /extraction/cv/run`

Uploads the CV and queues background extraction.

### `GET /onboarding/users/{user_id}/active`

Returns the current active onboarding state.

### `POST /onboarding/users/{user_id}/respond`

Resumes the graph from the current human-in-the-loop pause.

This single endpoint is used for:

- clarification answers
- final confirmation answers

## Human-in-the-loop pattern

The workflow uses `LangGraph interrupt/resume`.

That means:

- the server does not keep an HTTP request open while waiting for the user
- the graph pauses on a human question
- FastAPI returns the pending prompt to the client
- the next user answer resumes the same graph thread

Thread identity is the onboarding session id.

## Provider responsibilities

### Gemini

Used for:

- CV extraction
- clarification question decisions

Structured output is requested through provider-side schemas.

### DSPy

Used for:

- verify node via `ChainOfThought`
- search-plan node via `ChainOfThought`

The graph stores useful outputs from these nodes, but not internal reasoning traces.

## Logging

Logging is intentionally moderate:

- upload completed
- extraction started/completed
- clarification started/decided
- verification started/completed
- planning started/completed
- confirmation received

The code avoids noisy per-chunk or per-token logs.
