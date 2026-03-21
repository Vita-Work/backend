# Backend overview

Main building blocks:

- `src/extensions/` external infrastructure and provider integrations
- `src/modules/` product features and API-facing use-cases
- `src/workflows/` LangGraph orchestration
- `src/services/` shared external-service helpers when they do not belong to a single feature

Current extraction-related structure:

- `src/extensions/s3/` S3-compatible object storage integration
- `src/extensions/gemini/` Gemini extraction integration
- `src/modules/extraction/` CV upload endpoints and orchestration
- `src/workflows/search_setup/` extraction workflow graph and nodes

See [`docs/cv-extraction.md`](/Users/aidin/Projects/vita/backend/docs/cv-extraction.md) for the CV pipeline.
