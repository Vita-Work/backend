from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class StoredCvFileResponse(BaseModel):
    """Metadata about the stored CV file."""

    bucket: str
    key: str
    uri: str
    filename: str
    content_type: str
    extension: str
    size_bytes: int
    sha256: str


class ExtractionInputResponse(BaseModel):
    """Prepared extraction payload for the next workflow step."""

    strategy: Literal["model_file", "local_text"]
    inline_text_characters: int | None = None


class CvUploadResponse(BaseModel):
    """Response returned after accepting a CV for extraction."""

    file: StoredCvFileResponse
    extraction: ExtractionInputResponse


class CvExtractionWorkflowResponse(BaseModel):
    """Response returned after running the extraction workflow."""

    file: StoredCvFileResponse
    extraction: ExtractionInputResponse
    status: str
    extracted_profile: str
    missing_info: list[str]
    preference_hints: list[str]
    extraction_model: str | None = None


class CvExtractionWorkflowRunResponse(BaseModel):
    """Workflow run status and optional extraction result."""

    workflow_run_id: UUID
    file: StoredCvFileResponse
    extraction: ExtractionInputResponse
    status: str
    extracted_profile: str | None = None
    missing_info: list[str] = Field(default_factory=list)
    preference_hints: list[str] = Field(default_factory=list)
    extraction_model: str | None = None
    error_message: str | None = None
    ui_phase: str | None = None
    ui_label: str | None = None
    ui_description: str | None = None
    progress_percent: int | None = None
    progress_stage_index: int | None = None
    progress_stage_total: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_progress_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None


class ExtractionProgressEventResponse(BaseModel):
    workflow_run_id: UUID
    event_type: str
    ui_phase: str
    ui_label: str
    ui_description: str | None = None
    progress_percent: int | None = None
    progress_stage_index: int | None = None
    progress_stage_total: int | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
