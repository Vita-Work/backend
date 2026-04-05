from __future__ import annotations

from dataclasses import dataclass

from src.modules.auth.security import utcnow
from src.modules.extraction.models import ExtractionProgressEvent, ExtractionWorkflowRun
from src.modules.extraction.repository import ExtractionWorkflowRunsRepository


@dataclass(frozen=True)
class ExtractionUiStage:
    ui_phase: str
    ui_label: str
    ui_description: str
    progress_percent: int
    stage_index: int


EXTRACTION_UI_STAGES: dict[str, ExtractionUiStage] = {
    "upload_received": ExtractionUiStage(
        "upload_received",
        "CV uploaded",
        "Your file is safely uploaded and queued.",
        5,
        1,
    ),
    "file_stored": ExtractionUiStage(
        "file_stored",
        "Preparing your file",
        "We are preparing your CV for analysis.",
        15,
        2,
    ),
    "text_extraction": ExtractionUiStage(
        "text_extraction",
        "Reading your CV",
        "We are extracting the important details from your resume.",
        35,
        3,
    ),
    "cv_analysis": ExtractionUiStage(
        "cv_analysis",
        "Analyzing your experience",
        "We are understanding your background, skills, and preferences.",
        60,
        4,
    ),
    "building_profile": ExtractionUiStage(
        "building_profile",
        "Building your profile",
        "We are shaping your search profile and follow-up questions.",
        85,
        5,
    ),
    "ready_for_questions": ExtractionUiStage(
        "ready_for_questions",
        "Questions are ready",
        "Your profile is ready for the next onboarding step.",
        100,
        6,
    ),
    "failed": ExtractionUiStage(
        "failed",
        "Extraction failed",
        "Something interrupted CV extraction and needs attention.",
        100,
        6,
    ),
}
EXTRACTION_STAGE_TOTAL = 6


def update_extraction_progress(
    *,
    repository: ExtractionWorkflowRunsRepository,
    workflow_run: ExtractionWorkflowRun,
    event_type: str,
    phase: str,
    payload: dict[str, object] | None = None,
) -> None:
    stage = EXTRACTION_UI_STAGES[phase]
    ui_label = stage.ui_label
    ui_description = stage.ui_description
    if payload is not None:
        payload_label = payload.get("ui_label")
        payload_description = payload.get("ui_description")
        if isinstance(payload_label, str) and payload_label.strip():
            ui_label = payload_label
        if isinstance(payload_description, str) and payload_description.strip():
            ui_description = payload_description
    now = utcnow()
    workflow_run.ui_phase = stage.ui_phase
    workflow_run.ui_label = ui_label
    workflow_run.ui_description = ui_description
    workflow_run.progress_percent = stage.progress_percent
    workflow_run.progress_stage_index = stage.stage_index
    workflow_run.progress_stage_total = EXTRACTION_STAGE_TOTAL
    workflow_run.last_progress_at = now
    if getattr(workflow_run, "started_at", None) is None:
        workflow_run.started_at = now
    if phase in {"ready_for_questions", "failed"} or event_type == "error":
        workflow_run.finished_at = now
    if hasattr(repository, "add_progress_event"):
        repository.add_progress_event(
            workflow_run_id=workflow_run.id,
            user_id=workflow_run.user_id,
            event_type=event_type,
            ui_phase=stage.ui_phase,
            ui_label=ui_label,
            ui_description=ui_description,
            progress_percent=stage.progress_percent,
            progress_stage_index=stage.stage_index,
            progress_stage_total=EXTRACTION_STAGE_TOTAL,
            payload=payload,
        )


def get_extraction_error_code(
    *,
    progress_event: ExtractionProgressEvent | None,
) -> str | None:
    if progress_event is None:
        return None
    value = progress_event.payload.get("error_code")
    return value if isinstance(value, str) else None


def get_extraction_retryable(
    *,
    progress_event: ExtractionProgressEvent | None,
) -> bool | None:
    if progress_event is None:
        return None
    value = progress_event.payload.get("retryable")
    return value if isinstance(value, bool) else None
