from __future__ import annotations

from src.modules.auth.security import utcnow
from src.modules.extraction.models import ExtractionWorkflowRun
from src.modules.extraction.repository import ExtractionWorkflowRunsRepository

EXTRACTION_UI_STAGES: list[tuple[str, str, str, int, int]] = [
    ("upload_received", "CV uploaded", "Your file is safely uploaded and queued.", 5, 1),
    ("file_stored", "Preparing your file", "We are preparing your CV for analysis.", 15, 2),
    (
        "text_extraction",
        "Reading your CV",
        "We are extracting the important details from your resume.",
        35,
        3,
    ),
    (
        "cv_analysis",
        "Analyzing your experience",
        "We are understanding your background, skills, and preferences.",
        60,
        4,
    ),
    (
        "building_profile",
        "Building your profile",
        "We are shaping your search profile and follow-up questions.",
        85,
        5,
    ),
    (
        "ready_for_questions",
        "Questions are ready",
        "Your profile is ready for the next onboarding step.",
        100,
        6,
    ),
]
EXTRACTION_STAGE_TOTAL = len(EXTRACTION_UI_STAGES)


def update_extraction_progress(
    *,
    repository: ExtractionWorkflowRunsRepository,
    workflow_run: ExtractionWorkflowRun,
    event_type: str,
    phase: str,
    payload: dict[str, object] | None = None,
) -> None:
    phase_lookup = {item[0]: item for item in EXTRACTION_UI_STAGES}
    ui_phase, ui_label, ui_description, progress_percent, stage_index = phase_lookup[phase]
    now = utcnow()
    workflow_run.ui_phase = ui_phase
    workflow_run.ui_label = ui_label
    workflow_run.ui_description = ui_description
    workflow_run.progress_percent = progress_percent
    workflow_run.progress_stage_index = stage_index
    workflow_run.progress_stage_total = EXTRACTION_STAGE_TOTAL
    workflow_run.last_progress_at = now
    if getattr(workflow_run, "started_at", None) is None:
        workflow_run.started_at = now
    if phase == "ready_for_questions" or event_type == "error":
        workflow_run.finished_at = now
    if hasattr(repository, "add_progress_event"):
        repository.add_progress_event(
            workflow_run_id=workflow_run.id,
            user_id=workflow_run.user_id,
            event_type=event_type,
            ui_phase=ui_phase,
            ui_label=ui_label,
            ui_description=ui_description,
            progress_percent=progress_percent,
            progress_stage_index=stage_index,
            progress_stage_total=EXTRACTION_STAGE_TOTAL,
            payload=payload,
        )
