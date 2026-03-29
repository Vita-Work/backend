from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MatchGapReportPayload(BaseModel):
    overall_fit_score: int
    fit_label: str
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommended_positioning_angle: str
    apply_recommendation: str


class TailoredResumePayload(BaseModel):
    headline: str
    summary: str
    core_skills: list[str] = Field(default_factory=list)
    experience_bullets: list[str] = Field(default_factory=list)
    project_bullets: list[str] = Field(default_factory=list)
    education_notes: list[str] = Field(default_factory=list)
    final_resume_markdown: str


class ApplicationPacketPayload(BaseModel):
    cover_letter: str
    recruiter_intro_message: str
    interview_talking_points: list[str] = Field(default_factory=list)
    application_notes: list[str] = Field(default_factory=list)


class JobPackPayload(BaseModel):
    match_gap_report: MatchGapReportPayload
    tailoring_plan: dict[str, object] = Field(default_factory=dict)
    tailored_resume: TailoredResumePayload
    application_packet: ApplicationPacketPayload


class TrackedJobAiRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: str
    tracked_job_id: UUID
    run_type: Literal["match_gap", "job_pack"]
    status: str
    credit_cost: int
    source_onboarding_session_id: UUID | None = None
    source_profile_hash: str
    source_job_hash: str
    latest_successor_run_id: UUID | None = None
    error_message: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None


class MatchGapArtifactResponse(BaseModel):
    run: TrackedJobAiRunResponse
    report: MatchGapReportPayload


class JobPackArtifactResponse(BaseModel):
    run: TrackedJobAiRunResponse
    job_pack: JobPackPayload
