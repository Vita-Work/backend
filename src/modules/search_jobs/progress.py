from __future__ import annotations

from dataclasses import dataclass

from src.modules.auth.security import utcnow
from src.modules.search_jobs.models import SearchJobWorkflowRun
from src.modules.search_jobs.repository import SearchJobWorkflowRunsRepository


@dataclass(frozen=True)
class SearchDisplayStage:
    display_stage: str
    display_label: str
    display_description: str
    progress_order: int
    display_icon_key: str
    display_color_key: str


SEARCH_STAGE_MAP: dict[str, SearchDisplayStage] = {
    "queued": SearchDisplayStage(
        "queued", "Queued", "Your search is waiting to start.", 0, "clock", "slate"
    ),
    "planning": SearchDisplayStage(
        "planning",
        "Understanding your preferences",
        "We are turning your profile into a search plan.",
        1,
        "sparkles",
        "sky",
    ),
    "searching": SearchDisplayStage(
        "searching",
        "Scanning job boards",
        "We are checking the best sources for matching roles.",
        2,
        "search",
        "blue",
    ),
    "deduping": SearchDisplayStage(
        "deduping",
        "Removing duplicates",
        "We are cleaning the raw results before deeper review.",
        3,
        "filter",
        "amber",
    ),
    "fetching_details": SearchDisplayStage(
        "fetching_details",
        "Opening promising roles",
        "We are collecting the full details for the strongest listings.",
        4,
        "file-search",
        "violet",
    ),
    "unifying": SearchDisplayStage(
        "unifying",
        "Ranking your best matches",
        "We are selecting and scoring the final jobs for you.",
        5,
        "medal",
        "emerald",
    ),
    "completed": SearchDisplayStage(
        "completed",
        "Your jobs are ready",
        "Your results are ready to review and save.",
        6,
        "party-popper",
        "green",
    ),
    "failed": SearchDisplayStage(
        "failed",
        "Search stopped",
        "Something interrupted the search and needs attention.",
        6,
        "triangle-alert",
        "red",
    ),
}
SITE_DISPLAY_NAMES = {
    "indeed": "Indeed",
    "hh": "HH",
    "habr_career": "Habr Career",
    "linkedin": "LinkedIn",
    "getonbrd": "Get on Board",
    "computrabajo": "Computrabajo",
}


def update_search_progress(
    *,
    repository: SearchJobWorkflowRunsRepository,
    workflow_run: SearchJobWorkflowRun,
    event_type: str,
    internal_stage: str,
    site: str | None = None,
    payload: dict[str, object] | None = None,
) -> None:
    stage = SEARCH_STAGE_MAP.get(internal_stage, SEARCH_STAGE_MAP["searching"])
    site_display_name = SITE_DISPLAY_NAMES.get(site, site.title() if site else None)
    label = stage.display_label
    description = stage.display_description
    if site_display_name and internal_stage == "searching":
        label = f"Checking {site_display_name}"
        description = f"We are looking through {site_display_name} for matching openings."
    now = utcnow()
    workflow_run.current_internal_stage = internal_stage
    workflow_run.current_display_stage = stage.display_stage
    workflow_run.current_display_label = label
    workflow_run.current_display_description = description
    workflow_run.progress_stage_index = stage.progress_order
    workflow_run.progress_stage_total = 6
    workflow_run.progress_percent = min(100, max(0, int((stage.progress_order / 6) * 100)))
    workflow_run.last_progress_at = now
    if getattr(workflow_run, "started_at", None) is None:
        workflow_run.started_at = now
    if internal_stage in {"completed", "failed"}:
        workflow_run.finished_at = now
    if hasattr(repository, "add_progress_event"):
        repository.add_progress_event(
            workflow_run_id=workflow_run.id,
            user_id=workflow_run.user_id,
            event_type=event_type,
            internal_stage=internal_stage,
            display_stage=stage.display_stage,
            display_label=label,
            display_description=description,
            site=site,
            progress_order=stage.progress_order,
            display_icon_key=stage.display_icon_key,
            display_color_key=stage.display_color_key,
            site_display_name=site_display_name,
            payload=payload,
        )
