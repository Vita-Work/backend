from typing import Literal

from pydantic import BaseModel


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
