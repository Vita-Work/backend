from __future__ import annotations

from collections import Counter

from src.config import get_settings
from src.logger import get_logger
from src.workflows.search_job.schemas import SiteAgentResult, SiteJobDetail, UnifiedJob
from src.workflows.search_job.state import SearchJobState

logger = get_logger("workflows.search_job.finalize")


async def finalize_search_results_node(state: SearchJobState) -> dict[str, object]:
    """Finalize the full staged search-job workflow output."""
    deduped_jobs = _dedupe_and_sort_jobs(state.get("unified_jobs", []))
    settings = get_settings()
    final_jobs = deduped_jobs[: settings.search_job_unified_max_jobs]
    final_site_results = _build_final_site_results(
        site_results=state.get("site_results", []),
        deduped_details=state.get("deduped_details", []),
    )
    summary_markdown = _build_summary_markdown(
        site_results=final_site_results,
        jobs=final_jobs,
        notes=state.get("batch_notes", []),
        listing_candidates_count=len(state.get("listing_candidates", [])),
        detailed_jobs_count=len(state.get("deduped_details", [])),
    )
    logger.info(
        "search_job_finalize_completed",
        user_id=state["user_id"],
        onboarding_session_id=state["onboarding_session_id"],
        total_jobs_returned=len(final_jobs),
    )
    return {
        "status": "completed",
        "summary_markdown": summary_markdown,
        "final_jobs": final_jobs,
        "final_site_results": final_site_results,
    }


def _build_final_site_results(
    *,
    site_results: list[SiteAgentResult],
    deduped_details: list[SiteJobDetail],
) -> list[SiteAgentResult]:
    details_by_site: dict[str, list[SiteJobDetail]] = {}
    for detail in deduped_details:
        details_by_site.setdefault(detail.site, []).append(detail)

    final_results: list[SiteAgentResult] = []
    for site_result in site_results:
        final_results.append(
            site_result.model_copy(
                update={"selected_jobs": details_by_site.get(site_result.site, [])}
            )
        )
    return final_results


def _dedupe_and_sort_jobs(jobs: list[UnifiedJob]) -> list[UnifiedJob]:
    unique_jobs: dict[tuple[str, str], UnifiedJob] = {}
    for job in jobs:
        key = (job.site, job.job_url)
        current = unique_jobs.get(key)
        if current is None or _fit_rank(job.fit_level) > _fit_rank(current.fit_level):
            unique_jobs[key] = job

    return sorted(
        unique_jobs.values(),
        key=lambda job: (
            -_fit_rank(job.fit_level),
            (job.title or "").lower(),
            (job.company_name or "").lower(),
        ),
    )


def _fit_rank(fit_level: str) -> int:
    return {"high": 3, "middle": 2, "low": 1}.get(fit_level, 0)


def _build_summary_markdown(
    *,
    site_results: list[SiteAgentResult],
    jobs: list[UnifiedJob],
    notes: list[str],
    listing_candidates_count: int,
    detailed_jobs_count: int,
) -> str:
    skipped_sites = [result.site for result in site_results if result.status == "skipped"]
    fit_counts = Counter(job.fit_level for job in jobs)
    top_jobs = jobs[:10]
    top_lines = [
        (
            f"- [{job.fit_level}] {job.title or 'Unknown role'} at "
            f"{job.company_name or 'Unknown company'} ({job.site})"
            f": {job.why_apply}"
        )
        for job in top_jobs
    ]
    notes_block = "\n".join(f"- {note}" for note in notes[:10]) if notes else "- None"
    skipped_block = "\n".join(f"- {site}" for site in skipped_sites) if skipped_sites else "- None"
    top_block = "\n".join(top_lines) if top_lines else "- None"
    return (
        "# Search Job Summary\n\n"
        f"- Site results: {len(site_results)}\n"
        f"- Listing candidates collected: {listing_candidates_count}\n"
        f"- Detailed jobs kept: {detailed_jobs_count}\n"
        f"- Unified jobs returned: {len(jobs)}\n"
        f"- High fit: {fit_counts.get('high', 0)}\n"
        f"- Middle fit: {fit_counts.get('middle', 0)}\n"
        f"- Low fit: {fit_counts.get('low', 0)}\n\n"
        "## Top Matches\n"
        f"{top_block}\n\n"
        "## Skipped Sites\n"
        f"{skipped_block}\n\n"
        "## Notes\n"
        f"{notes_block}"
    )
