from __future__ import annotations

from src.workflows.search_job.dedupe import normalize_text


def build_job_fingerprint(
    *,
    title: str | None,
    company_name: str | None,
    location: str | None,
) -> str | None:
    """Build a stable lightweight fingerprint for cross-run job history checks."""
    normalized_title = normalize_text(title)
    normalized_company = normalize_text(company_name)
    normalized_location = normalize_text(location)
    if not normalized_title or not normalized_company:
        return None
    return "|".join([normalized_title, normalized_company, normalized_location])
