from __future__ import annotations

from src.modules.extraction.models import ExtractionProgressEvent, ExtractionWorkflowRun
from src.modules.extraction.progress import get_extraction_error_code, get_extraction_retryable
from src.modules.extraction.schemas import (
    CvExtractionWorkflowRunResponse,
    ExtractionInputResponse,
    StoredCvFileResponse,
)


def build_extraction_workflow_run_response(
    *,
    workflow_run: ExtractionWorkflowRun,
    failure_event: ExtractionProgressEvent | None = None,
) -> CvExtractionWorkflowRunResponse:
    return CvExtractionWorkflowRunResponse(
        workflow_run_id=workflow_run.id,
        file=StoredCvFileResponse(
            bucket=workflow_run.storage_bucket,
            key=workflow_run.storage_key,
            uri=workflow_run.storage_uri,
            filename=workflow_run.cv_filename,
            content_type=workflow_run.cv_content_type,
            extension=workflow_run.cv_extension,
            size_bytes=workflow_run.cv_size_bytes,
            sha256=workflow_run.cv_sha256,
        ),
        extraction=ExtractionInputResponse(
            strategy=workflow_run.extraction_strategy,
            inline_text_characters=workflow_run.inline_text_characters,
        ),
        status=workflow_run.status,
        extracted_profile=workflow_run.extracted_profile,
        missing_info=workflow_run.missing_info or [],
        preference_hints=workflow_run.preference_hints or [],
        extraction_model=workflow_run.extraction_model,
        error_message=workflow_run.error_message,
        error_code=get_extraction_error_code(progress_event=failure_event),
        retryable=get_extraction_retryable(progress_event=failure_event),
        ui_phase=workflow_run.ui_phase,
        ui_label=workflow_run.ui_label,
        ui_description=workflow_run.ui_description,
        progress_percent=workflow_run.progress_percent,
        progress_stage_index=workflow_run.progress_stage_index,
        progress_stage_total=workflow_run.progress_stage_total,
        started_at=workflow_run.started_at,
        finished_at=workflow_run.finished_at,
        last_progress_at=workflow_run.last_progress_at,
        created_at=workflow_run.created_at,
        updated_at=workflow_run.updated_at,
    )
