from __future__ import annotations

from functools import lru_cache

import dspy
from pydantic import BaseModel, Field, ValidationError

from src.config import get_settings
from src.extensions.gemini import GeminiIntegrationError
from src.logger import get_logger
from src.workflows.job_application.signatures.match_gap import MatchGapReportSignature
from src.workflows.job_application.signatures.tailor_plan import (
    TailorResumePlanSignature,
)
from src.workflows.search_job.schemas import SearchExecutionPlan
from src.workflows.search_job.signatures.execution_plan import SearchJobExecutionPlanSignature
from src.workflows.search_setup.signatures.search_plan import SearchPlanSignature
from src.workflows.search_setup.signatures.verify_profile import VerifyProfileSignature

logger = get_logger("integrations.dspy")


class DspyIntegrationError(RuntimeError):
    """Raised when DSPy integration cannot complete a request."""


class VerifyProfileResult(BaseModel):
    """Structured verification output."""

    verification_score: float
    is_verified: bool
    verification_summary: str
    remaining_gaps: list[str] = Field(default_factory=list)


class SearchPlanResult(BaseModel):
    """Structured search planning output."""

    search_strategy_summary: str
    soft_preferences: list[str] = Field(default_factory=list)
    hard_preferences: list[str] = Field(default_factory=list)


class SearchJobExecutionPlanResult(SearchExecutionPlan):
    """Structured runtime execution plan for search_job."""


class MatchGapReportResult(BaseModel):
    """Structured fit analysis for one tracked job."""

    overall_fit_score: int
    fit_label: str
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommended_positioning_angle: str
    apply_recommendation: str


class TailorResumePlanResult(BaseModel):
    """Compact planning output for job-specific tailoring."""

    target_headline: str
    target_summary_angle: str
    must_emphasize: list[str] = Field(default_factory=list)
    must_downplay: list[str] = Field(default_factory=list)
    must_include_keywords: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    experience_reordering_strategy: str
    cover_letter_angle: str
    recruiter_intro_angle: str


class DspySearchSetupService:
    """Shared DSPy modules for verification and planning."""

    def __init__(self, *, api_key: str, model: str) -> None:
        resolved_model = model if "/" in model else f"gemini/{model}"
        self.model_name = resolved_model
        self.lm = dspy.LM(resolved_model, api_key=api_key, temperature=0.1, cache=True)
        self.verify_profile = dspy.ChainOfThought(VerifyProfileSignature)
        self.verify_profile.set_lm(self.lm)
        self.search_plan = dspy.ChainOfThought(SearchPlanSignature)
        self.search_plan.set_lm(self.lm)
        self.search_job_plan = dspy.ChainOfThought(SearchJobExecutionPlanSignature)
        self.search_job_plan.set_lm(self.lm)
        self.match_gap_report = dspy.ChainOfThought(MatchGapReportSignature)
        self.match_gap_report.set_lm(self.lm)
        self.tailor_resume_plan = dspy.ChainOfThought(TailorResumePlanSignature)
        self.tailor_resume_plan.set_lm(self.lm)

    async def verify_candidate_profile(
        self,
        *,
        user_profile: str,
        missing_info: list[str],
        clarification_chat: str,
    ) -> VerifyProfileResult:
        """Verify whether the candidate context is sufficient for planning."""
        try:
            with dspy.settings.context(lm=self.lm):
                prediction = await self.verify_profile.acall(
                    user_profile=user_profile,
                    missing_info=missing_info,
                    clarification_chat=clarification_chat,
                )
            return VerifyProfileResult.model_validate(
                {
                    "verification_score": prediction.verification_score,
                    "is_verified": prediction.is_verified,
                    "verification_summary": prediction.verification_summary,
                    "remaining_gaps": prediction.remaining_gaps,
                }
            )
        except ValidationError as exc:
            raise DspyIntegrationError("DSPy returned an invalid verification payload.") from exc
        except Exception as exc:
            raise DspyIntegrationError("DSPy verification failed.") from exc

    async def build_search_plan(
        self,
        *,
        planning_context: str,
        user_profile: str,
    ) -> SearchPlanResult:
        """Build a structured search plan from the clarified profile context."""
        try:
            with dspy.settings.context(lm=self.lm):
                prediction = await self.search_plan.acall(
                    planning_context=planning_context,
                    user_profile=user_profile,
                )
            return SearchPlanResult.model_validate(
                {
                    "search_strategy_summary": prediction.search_strategy_summary,
                    "soft_preferences": prediction.soft_preferences,
                    "hard_preferences": prediction.hard_preferences,
                }
            )
        except ValidationError as exc:
            raise DspyIntegrationError("DSPy returned an invalid search-plan payload.") from exc
        except Exception as exc:
            raise DspyIntegrationError("DSPy search planning failed.") from exc

    async def build_search_job_execution_plan(
        self,
        *,
        search_strategy_summary: str,
        hard_preferences: list[str],
        soft_preferences: list[str],
        available_sites: list[str],
    ) -> SearchJobExecutionPlanResult:
        """Build the runtime execution plan for one search-job run."""
        try:
            with dspy.settings.context(lm=self.lm):
                prediction = await self.search_job_plan.acall(
                    search_strategy_summary=search_strategy_summary,
                    hard_preferences=hard_preferences,
                    soft_preferences=soft_preferences,
                    available_sites=available_sites,
                )
            return SearchJobExecutionPlanResult.model_validate(
                {
                    "queries": prediction.queries,
                    "include_keywords": prediction.include_keywords,
                    "exclude_keywords": prediction.exclude_keywords,
                    "locations": prediction.locations,
                    "remote_only": prediction.remote_only,
                    "salary_from": prediction.salary_from,
                    "seniority": prediction.seniority,
                    "target_sites": prediction.target_sites,
                    "notes": prediction.notes,
                }
            )
        except ValidationError as exc:
            raise DspyIntegrationError("DSPy returned an invalid search-job plan payload.") from exc
        except Exception as exc:
            raise DspyIntegrationError("DSPy search-job planning failed.") from exc

    async def build_match_gap_report(
        self,
        *,
        user_profile: str,
        verification_summary: str,
        search_strategy_summary: str,
        hard_preferences: list[str],
        soft_preferences: list[str],
        job_title: str,
        company_name: str,
        job_description: str,
        job_skills: list[str],
        why_apply_snapshot: str,
        fit_level: str,
    ) -> MatchGapReportResult:
        try:
            with dspy.settings.context(lm=self.lm):
                prediction = await self.match_gap_report.acall(
                    user_profile=user_profile,
                    verification_summary=verification_summary,
                    search_strategy_summary=search_strategy_summary,
                    hard_preferences=hard_preferences,
                    soft_preferences=soft_preferences,
                    job_title=job_title,
                    company_name=company_name,
                    job_description=job_description,
                    job_skills=job_skills,
                    why_apply_snapshot=why_apply_snapshot,
                    fit_level=fit_level,
                )
            return MatchGapReportResult.model_validate(
                {
                    "overall_fit_score": prediction.overall_fit_score,
                    "fit_label": prediction.fit_label,
                    "strengths": prediction.strengths,
                    "gaps": prediction.gaps,
                    "missing_keywords": prediction.missing_keywords,
                    "risks": prediction.risks,
                    "recommended_positioning_angle": prediction.recommended_positioning_angle,
                    "apply_recommendation": prediction.apply_recommendation,
                }
            )
        except ValidationError as exc:
            raise DspyIntegrationError("DSPy returned an invalid match-gap payload.") from exc
        except Exception as exc:
            raise DspyIntegrationError("DSPy match-gap analysis failed.") from exc

    async def build_tailor_resume_plan(
        self,
        *,
        user_profile: str,
        verification_summary: str,
        search_strategy_summary: str,
        hard_preferences: list[str],
        soft_preferences: list[str],
        job_title: str,
        company_name: str,
        job_description: str,
        job_skills: list[str],
        why_apply_snapshot: str,
        fit_level: str,
        match_gap_report: str,
    ) -> TailorResumePlanResult:
        try:
            with dspy.settings.context(lm=self.lm):
                prediction = await self.tailor_resume_plan.acall(
                    user_profile=user_profile,
                    verification_summary=verification_summary,
                    search_strategy_summary=search_strategy_summary,
                    hard_preferences=hard_preferences,
                    soft_preferences=soft_preferences,
                    job_title=job_title,
                    company_name=company_name,
                    job_description=job_description,
                    job_skills=job_skills,
                    why_apply_snapshot=why_apply_snapshot,
                    fit_level=fit_level,
                    match_gap_report=match_gap_report,
                )
            return TailorResumePlanResult.model_validate(
                {
                    "target_headline": prediction.target_headline,
                    "target_summary_angle": prediction.target_summary_angle,
                    "must_emphasize": prediction.must_emphasize,
                    "must_downplay": prediction.must_downplay,
                    "must_include_keywords": prediction.must_include_keywords,
                    "forbidden_claims": prediction.forbidden_claims,
                    "experience_reordering_strategy": prediction.experience_reordering_strategy,
                    "cover_letter_angle": prediction.cover_letter_angle,
                    "recruiter_intro_angle": prediction.recruiter_intro_angle,
                }
            )
        except ValidationError as exc:
            raise DspyIntegrationError("DSPy returned an invalid tailoring-plan payload.") from exc
        except Exception as exc:
            raise DspyIntegrationError("DSPy tailoring-plan generation failed.") from exc


@lru_cache(maxsize=1)
def get_dspy_search_setup_service() -> DspySearchSetupService:
    """Build and cache the shared DSPy service."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise GeminiIntegrationError("Missing required Gemini setting: GEMINI_API_KEY")

    return DspySearchSetupService(
        api_key=settings.gemini_api_key,
        model=settings.dspy_model or settings.gemini_model,
    )
