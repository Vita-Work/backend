from datetime import datetime

from pydantic import BaseModel
from src.modules.extraction.schemas import ExtractionInputResponse, StoredCvFileResponse


class CreateResumeIntakeResponse(BaseModel):
    intake_token: str
    file: StoredCvFileResponse
    extraction: ExtractionInputResponse
    status: str
    expires_at: datetime


class PendingResumeIntakeResponse(BaseModel):
    file: StoredCvFileResponse
    extraction: ExtractionInputResponse
    status: str
    expires_at: datetime
    claimed_at: datetime | None
    created_at: datetime


class ClaimResumeIntakeRequest(BaseModel):
    intake_token: str
