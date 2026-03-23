from __future__ import annotations

from functools import lru_cache

import dspy
from pydantic import BaseModel, Field, ValidationError

from src.config import get_settings
from src.extensions.gemini import GeminiIntegrationError
from src.logger import get_logger
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
