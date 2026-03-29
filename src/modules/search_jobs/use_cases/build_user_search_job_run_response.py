from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.billing.repository import (
    BillingAccessPassesRepository,
    BillingSubscriptionsRepository,
)
from src.modules.billing.service import build_billing_entitlements, limit_visible_search_jobs
from src.modules.job_tracker.repository import TrackedJobsRepository
from src.modules.job_tracker.schemas import JobTrackerListQuery
from src.modules.job_tracker.service import normalize_job_url
from src.modules.search_jobs.models import SearchJobWorkflowRun
from src.modules.search_jobs.presenters import build_search_job_workflow_run_response
from src.modules.search_jobs.schemas import SearchJobWorkflowRunResponse

SITE_DISPLAY_NAMES: dict[str, str] = {
    "indeed": "Indeed",
    "hh": "HH",
    "habr_career": "Habr Career",
    "getonbrd": "Get on Board",
    "computrabajo": "Computrabajo",
    "linkedin": "LinkedIn",
}


async def build_user_search_job_run_response(
    *,
    session: AsyncSession,
    user_id: str,
    workflow_run: SearchJobWorkflowRun,
) -> SearchJobWorkflowRunResponse:
    subscription = await BillingSubscriptionsRepository(session=session).get_by_user_id(
        user_id=user_id
    )
    access_pass = await BillingAccessPassesRepository(session=session).get_active_for_user(
        user_id=user_id
    )
    entitlements = build_billing_entitlements(subscription=subscription, access_pass=access_pass)
    response = build_search_job_workflow_run_response(workflow_run=workflow_run)
    response_jobs_by_key = {
        job_key: job
        for job in response.jobs
        if (job_key := _job_lookup_key(job.job_url)) is not None
    }

    tracked_jobs = await TrackedJobsRepository(session=session).list_jobs_for_user(
        user_id=user_id,
        query=JobTrackerListQuery(archived=False),
    )
    tracked_jobs_by_url = {
        job.source_job_url: job
        for job in tracked_jobs
        if job.source_job_url and job.archived_at is None
    }

    visible_jobs = limit_visible_search_jobs(
        jobs=workflow_run.jobs or [],
        entitlements=entitlements,
    )
    hidden_jobs_count = max(len(workflow_run.jobs or []) - len(visible_jobs), 0)

    enriched_jobs = []
    for job_dict in visible_jobs:
        job = response_jobs_by_key.get(_job_lookup_key(job_dict.get("job_url")))
        if job is None:
            continue

        tracked_job = tracked_jobs_by_url.get(_job_lookup_key(job.job_url))
        enriched_jobs.append(
            job.model_copy(
                update={
                    "is_saved_to_tracker": tracked_job is not None,
                    "tracked_job_id": str(tracked_job.id) if tracked_job is not None else None,
                    "site_display_name": SITE_DISPLAY_NAMES.get(
                        job.site,
                        job.site.title() if job.site else None,
                    ),
                    "site_logo_key": job.site,
                    "display_badge_label": job.fit_level.title() if job.fit_level else None,
                }
            )
        )

    return response.model_copy(
        update={
            "jobs": enriched_jobs,
            "billing_plan": entitlements.plan_code,
            "visible_jobs_count": len(enriched_jobs),
            "hidden_jobs_count": hidden_jobs_count,
            "viewer_job_limit": entitlements.search_results_limit,
        }
    )


def _job_lookup_key(job_url: str | None) -> str | None:
    return normalize_job_url(job_url) or job_url
