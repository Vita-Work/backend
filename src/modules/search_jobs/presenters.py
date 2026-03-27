from __future__ import annotations

from src.modules.search_jobs.models import SearchJobWorkflowRun
from src.modules.search_jobs.schemas import SearchJobWorkflowRunResponse
from src.workflows.search_job.schemas import SiteAgentResult, UnifiedJob


def build_search_job_workflow_run_response(
    *,
    workflow_run: SearchJobWorkflowRun,
) -> SearchJobWorkflowRunResponse:
    return SearchJobWorkflowRunResponse(
        workflow_run_id=workflow_run.id,
        onboarding_session_id=workflow_run.onboarding_session_id,
        user_id=workflow_run.user_id,
        status=workflow_run.status,
        search_strategy_summary=workflow_run.search_strategy_summary,
        hard_preferences=workflow_run.hard_preferences or [],
        soft_preferences=workflow_run.soft_preferences or [],
        source_sites=workflow_run.source_sites or [],
        monitoring_mode=workflow_run.monitoring_mode,
        total_site_results=workflow_run.total_site_results,
        total_jobs_found=workflow_run.total_jobs_found,
        total_jobs_returned=workflow_run.total_jobs_returned,
        summary_markdown=workflow_run.summary_markdown,
        jobs=[UnifiedJob.model_validate(job) for job in (workflow_run.jobs or [])],
        site_results=[
            SiteAgentResult.model_validate(site_result)
            for site_result in (workflow_run.site_results or [])
        ],
        notes=workflow_run.notes or [],
        search_model=workflow_run.search_model,
        unification_model=workflow_run.unification_model,
        error_message=workflow_run.error_message,
        current_internal_stage=workflow_run.current_internal_stage,
        current_display_stage=workflow_run.current_display_stage,
        current_display_label=workflow_run.current_display_label,
        current_display_description=workflow_run.current_display_description,
        progress_percent=workflow_run.progress_percent,
        progress_stage_index=workflow_run.progress_stage_index,
        progress_stage_total=workflow_run.progress_stage_total,
        started_at=workflow_run.started_at,
        finished_at=workflow_run.finished_at,
        last_progress_at=workflow_run.last_progress_at,
        created_at=workflow_run.created_at,
        updated_at=workflow_run.updated_at,
    )
