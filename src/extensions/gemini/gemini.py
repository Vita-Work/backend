from __future__ import annotations

import asyncio
import json
import random
from functools import lru_cache
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError

from src.config import get_settings
from src.logger import get_logger
from src.workflows.search_job.schemas import UnifiedJob

logger = get_logger("integrations.gemini")

FILE_POLL_INTERVAL_SECONDS = 1.0
FILE_POLL_TIMEOUT_SECONDS = 60.0


class GeminiIntegrationError(RuntimeError):
    """Raised when Gemini integration cannot complete a request."""


class CvExtractionResult(BaseModel):
    """Structured extraction result returned by Gemini."""

    extracted_profile: str
    missing_info: list[str] = Field(default_factory=list)
    preference_hints: list[str] = Field(default_factory=list)


class ClarificationDecision(BaseModel):
    """Structured clarification decision returned by Gemini."""

    needs_more_context: bool
    question: str | None = None
    missing_info: list[str] = Field(default_factory=list)
    preference_hints: list[str] = Field(default_factory=list)


class UnifiedJobsBatchResult(BaseModel):
    """Structured unified-job annotation result for one batch."""

    jobs: list[UnifiedJob] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class GeminiCvExtractionService:
    """Run CV extraction prompts against Gemini."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
    ) -> None:
        self.api_key = api_key
        self.model = model

    async def extract_from_text(self, *, cv_text: str) -> CvExtractionResult:
        """Extract a structured candidate profile from plain CV text."""
        return await self._generate_with_contents(contents=[self._extraction_prompt(), cv_text])

    async def extract_from_file(self, *, file_path: Path, mime_type: str) -> CvExtractionResult:
        """Extract a structured candidate profile from an uploaded CV file."""
        async with genai.Client(api_key=self.api_key).aio as client:
            uploaded_file = await client.files.upload(
                file=file_path,
                config=types.UploadFileConfig(
                    mime_type=mime_type,
                    display_name=file_path.name,
                ),
            )

            uploaded_file = await self._wait_until_file_active(
                client=client,
                file_name=uploaded_file.name,
            )
            logger.info(
                "gemini_file_upload_ready",
                file_name=uploaded_file.name,
                mime_type=uploaded_file.mime_type,
                model=self.model,
            )

            try:
                response = await client.models.generate_content(
                    model=self.model,
                    contents=[
                        self._extraction_prompt(),
                        types.Part.from_uri(
                            file_uri=uploaded_file.uri,
                            mime_type=uploaded_file.mime_type,
                        ),
                    ],
                    config=self._generation_config(),
                )
            finally:
                await client.files.delete(name=uploaded_file.name)

        return self._parse_response(response=response)

    async def decide_clarification(
        self,
        *,
        extracted_profile: str,
        missing_info: list[str],
        preference_hints: list[str],
        clarification_turns: list[dict[str, str]],
        verification_summary: str | None = None,
    ) -> ClarificationDecision:
        """Decide whether another clarification question is needed."""
        turns_text = "\n".join(
            f"Q: {turn['question']}\nA: {turn['answer']}" for turn in clarification_turns
        ).strip()
        if not turns_text:
            turns_text = "No clarification answers yet."

        contents = [
            self._clarification_prompt(),
            (
                f"Extracted profile:\n{extracted_profile}\n\n"
                f"Current missing info:\n{self._format_list(missing_info)}\n\n"
                f"Current preference hints:\n{self._format_list(preference_hints)}\n\n"
                f"Clarification history:\n{turns_text}\n\n"
                f"Verification summary:\n{verification_summary or 'No verification summary yet.'}"
            ),
        ]
        async with genai.Client(api_key=self.api_key).aio as client:
            response = await client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                    response_schema=ClarificationDecision,
                ),
            )
        return self._parse_clarification_response(response=response)

    async def _generate_with_contents(
        self, *, contents: list[str | types.File]
    ) -> CvExtractionResult:
        async with genai.Client(api_key=self.api_key).aio as client:
            response = await client.models.generate_content(
                model=self.model,
                contents=contents,
                config=self._generation_config(),
            )
        return self._parse_response(response=response)

    async def _wait_until_file_active(
        self,
        *,
        client,
        file_name: str,
    ):
        deadline = asyncio.get_running_loop().time() + FILE_POLL_TIMEOUT_SECONDS
        current_file = await client.files.get(name=file_name)

        while current_file.state == types.FileState.PROCESSING:
            if asyncio.get_running_loop().time() >= deadline:
                raise GeminiIntegrationError("Gemini file processing timed out.")

            await asyncio.sleep(FILE_POLL_INTERVAL_SECONDS)
            current_file = await client.files.get(name=file_name)

        if current_file.state != types.FileState.ACTIVE:
            raise GeminiIntegrationError(
                f"Gemini file upload failed with state={current_file.state}."
            )

        return current_file

    def _generation_config(self) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
            response_schema=CvExtractionResult,
        )

    def _parse_response(self, *, response) -> CvExtractionResult:
        try:
            if isinstance(response.parsed, CvExtractionResult):
                return response.parsed
            if isinstance(response.parsed, dict):
                return CvExtractionResult.model_validate(response.parsed)
            if response.text:
                return CvExtractionResult.model_validate_json(response.text)
        except ValidationError as exc:
            raise GeminiIntegrationError("Gemini returned an invalid extraction payload.") from exc

        raise GeminiIntegrationError("Gemini returned an empty extraction response.")

    def _parse_clarification_response(self, *, response) -> ClarificationDecision:
        try:
            if isinstance(response.parsed, ClarificationDecision):
                return response.parsed
            if isinstance(response.parsed, dict):
                return ClarificationDecision.model_validate(response.parsed)
            if response.text:
                return ClarificationDecision.model_validate_json(response.text)
        except ValidationError as exc:
            raise GeminiIntegrationError(
                "Gemini returned an invalid clarification payload."
            ) from exc

        raise GeminiIntegrationError("Gemini returned an empty clarification response.")

    @staticmethod
    def _extraction_prompt() -> str:
        return (
            "You are extracting a hiring profile from a candidate CV or resume. "
            "Return structured JSON with three fields only: extracted_profile, missing_info, "
            "preference_hints. "
            "extracted_profile must be a dense but readable profile of the candidate, covering "
            "summary, experience, skills, domains, seniority, education, achievements, likely "
            "role fit, and any clearly supported inferred preferences or constraints. "
            "Use the dominant language of the CV if obvious; otherwise use English. "
            "missing_info must contain concise factual gaps that a clarification step should ask "
            "the candidate next, such as location preference, remote/on-site preference, "
            "compensation expectations, notice period, visa, employment type, industry preference, "
            "or role constraints. "
            "preference_hints must contain short inferred hints from the CV only, without guessing "
            "beyond the evidence. "
            "Do not mention that you are reading a file. Do not wrap the output in markdown."
        )

    @staticmethod
    def _clarification_prompt() -> str:
        return (
            "You are deciding the next clarification step after CV extraction for a hiring "
            "workflow. "
            "Return structured JSON with four fields only: needs_more_context, question, "
            "missing_info, preference_hints. "
            "If the candidate context is still missing important job-search constraints or "
            "preferences, set needs_more_context=true and ask exactly one concise, high-value next "
            "question in question. "
            "If there is already enough context to continue, set needs_more_context=false and "
            "question=null. "
            "Update missing_info to contain only the still-open factual gaps. "
            "Update preference_hints to reflect only evidence from the CV and clarification "
            "answers. "
            "Do not repeat a question that has already been answered in the clarification "
            "history, even if the answer conflicts with the CV. "
            "When the user's latest explicit correction conflicts with the CV, treat the user's "
            "latest explicit correction as more authoritative for future questions. "
            "Prefer questions about location, remote/on-site, employment type, salary "
            "expectations, "
            "notice period, visa/work authorization, target roles, industry preferences, and hard "
            "constraints. "
            "Do not ask multiple questions at once. Match the dominant language of the profile or "
            "clarification history when obvious. Do not wrap the output in markdown."
        )

    @staticmethod
    def _format_list(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items) if items else "- None"


class GeminiJobSearchService:
    """Batch-unify shortlisted jobs into a stable cross-site schema."""

    def __init__(self, *, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model
        settings = get_settings()
        self.request_timeout_seconds = float(settings.gemini_request_timeout_seconds)
        self.max_retries = settings.gemini_max_retries

    async def unify_jobs_batch(
        self,
        *,
        search_strategy_summary: str,
        hard_preferences: list[str],
        soft_preferences: list[str],
        batch_jobs: list[dict[str, object]],
    ) -> UnifiedJobsBatchResult:
        """Annotate one batch of shortlisted jobs with fit, reasons, and risks."""
        sanitized_batch_jobs = [self._sanitize_batch_job(job) for job in batch_jobs]
        contents = [
            self._unification_prompt(),
            json.dumps(
                {
                    "search_strategy_summary": search_strategy_summary,
                    "hard_preferences": hard_preferences,
                    "soft_preferences": soft_preferences,
                    "batch_jobs": sanitized_batch_jobs,
                },
                ensure_ascii=False,
            ),
        ]
        response = await self._generate_with_retry(contents=contents)
        return self._parse_unified_jobs_batch_response(response=response)

    async def _generate_with_retry(self, *, contents: list[str]) -> object:
        attempts = self.max_retries + 1
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                async with genai.Client(api_key=self.api_key).aio as client:
                    return await asyncio.wait_for(
                        client.models.generate_content(
                            model=self.model,
                            contents=contents,
                            config=types.GenerateContentConfig(
                                temperature=0.1,
                                response_mime_type="application/json",
                                response_schema=UnifiedJobsBatchResult,
                            ),
                        ),
                        timeout=self.request_timeout_seconds,
                    )
            except Exception as exc:
                last_exc = exc
                if not self._is_retryable_provider_error(exc) or attempt >= attempts:
                    raise
                delay_seconds = min(8.0, (2 ** (attempt - 1)) + random.uniform(0.0, 0.5))
                logger.warning(
                    "gemini_unification_retry_scheduled",
                    retry_attempt=attempt,
                    provider_timeout_detected=True,
                    delay_seconds=round(delay_seconds, 2),
                    model=self.model,
                    error=str(exc),
                )
                await asyncio.sleep(delay_seconds)

        raise GeminiIntegrationError(f"Gemini unified-jobs batch failed after retries: {last_exc}")

    def _parse_unified_jobs_batch_response(self, *, response) -> UnifiedJobsBatchResult:
        try:
            if isinstance(response.parsed, UnifiedJobsBatchResult):
                return response.parsed
            if isinstance(response.parsed, dict):
                return UnifiedJobsBatchResult.model_validate(response.parsed)
            if response.text:
                return UnifiedJobsBatchResult.model_validate_json(response.text)
        except ValidationError as exc:
            raise GeminiIntegrationError(
                "Gemini returned an invalid unified-jobs batch payload."
            ) from exc

        raise GeminiIntegrationError("Gemini returned an empty unified-jobs batch response.")

    @staticmethod
    def _is_retryable_provider_error(exc: Exception) -> bool:
        message = str(exc).upper()
        return any(
            marker in message
            for marker in (
                "504",
                "DEADLINE_EXCEEDED",
                "SERVICE UNAVAILABLE",
                "UNAVAILABLE",
                "INTERNAL",
                "TIMEOUT",
            )
        )

    @staticmethod
    def _unification_prompt() -> str:
        return (
            "You are unifying shortlisted jobs from multiple job sites into a stable "
            "search funnel. "
            "Return JSON with two fields only: jobs and notes. "
            "For every input batch job, return exactly one output job in jobs. "
            "Preserve factual job fields from the input whenever present. "
            "Add why_apply as one concise explanation of why the user should consider the role. "
            "Add risks as concise bullets highlighting mismatches, uncertainty, or downsides. "
            "Add fit_level as one of: low, middle, high. "
            "Fit level must reflect the approved search strategy summary and "
            "hard preferences, "
            "and soft preferences. "
            "Do not invent facts not supported by the input. "
            "Keep notes short and use them only for batch-level caveats."
        )

    @staticmethod
    def _sanitize_batch_job(job: dict[str, object]) -> dict[str, object]:
        sanitized = {key: value for key, value in job.items() if key != "raw_meta"}
        for field_name in ("description", "company_about"):
            value = sanitized.get(field_name)
            if isinstance(value, str):
                sanitized[field_name] = value[:4000]
        company_contacts = sanitized.get("company_contacts")
        if isinstance(company_contacts, list):
            sanitized["company_contacts"] = company_contacts[:5]
        skills = sanitized.get("skills")
        if isinstance(skills, list):
            sanitized["skills"] = skills[:20]
        return sanitized


@lru_cache(maxsize=1)
def get_gemini_cv_extraction_service() -> GeminiCvExtractionService:
    """Build and cache the shared Gemini CV extraction service."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise GeminiIntegrationError("Missing required Gemini setting: GEMINI_API_KEY")

    return GeminiCvExtractionService(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
    )


@lru_cache(maxsize=1)
def get_gemini_job_search_service() -> GeminiJobSearchService:
    """Build and cache the shared Gemini job-search service."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise GeminiIntegrationError("Missing required Gemini setting: GEMINI_API_KEY")

    return GeminiJobSearchService(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
    )
