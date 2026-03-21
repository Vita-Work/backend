# Backend overview

Main building blocks:

- `src/extensions/` external infrastructure and provider integrations
- `src/modules/` product features and API-facing use-cases
- `src/workflows/` LangGraph orchestration

Current extraction-related structure:

- `src/extensions/s3/` S3-compatible object storage integration
- `src/extensions/gemini/` Gemini extraction integration
- `src/extensions/dspy/` DSPy-based verification and planning modules
- `src/extensions/arq/` background jobs and Redis queue integration
- `src/modules/extraction/` CV upload endpoints and orchestration
- `src/modules/onboarding/` persisted onboarding state and HITL endpoints
- `src/modules/users/` user CRUD primitives
- `src/workflows/search_setup/` unified onboarding workflow graph and nodes

See [`docs/cv-extraction.md`](/Users/aidin/Projects/vita/backend/docs/cv-extraction.md) for the CV pipeline and [`docs/search-setup-architecture.md`](/Users/aidin/Projects/vita/backend/docs/search-setup-architecture.md) for the end-to-end workflow.
