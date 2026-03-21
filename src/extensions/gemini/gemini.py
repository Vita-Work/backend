from __future__ import annotations

import asyncio
from functools import lru_cache
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from src.config import get_settings
from src.logger import get_logger

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


class GeminiCvExtractionService:
    """Run CV extraction prompts against Gemini."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        api_version: str,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.api_version = api_version

    async def extract_from_text(self, *, cv_text: str) -> CvExtractionResult:
        """Extract a structured candidate profile from plain CV text."""
        return await self._generate_with_contents(contents=[self._extraction_prompt(), cv_text])

    async def extract_from_file(self, *, file_path: Path, mime_type: str) -> CvExtractionResult:
        """Extract a structured candidate profile from an uploaded CV file."""
        async with genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(api_version=self.api_version),
        ).aio as client:
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
                    contents=[self._extraction_prompt(), uploaded_file],
                    config=self._generation_config(),
                )
            finally:
                await client.files.delete(name=uploaded_file.name)

        return self._parse_response(response=response)

    async def _generate_with_contents(
        self, *, contents: list[str | types.File]
    ) -> CvExtractionResult:
        async with genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(api_version=self.api_version),
        ).aio as client:
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
        if isinstance(response.parsed, CvExtractionResult):
            return response.parsed
        if isinstance(response.parsed, dict):
            return CvExtractionResult.model_validate(response.parsed)
        if response.text:
            return CvExtractionResult.model_validate_json(response.text)
        raise GeminiIntegrationError("Gemini returned an empty extraction response.")

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


@lru_cache(maxsize=1)
def get_gemini_cv_extraction_service() -> GeminiCvExtractionService:
    """Build and cache the shared Gemini CV extraction service."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise GeminiIntegrationError("Missing required Gemini setting: GEMINI_API_KEY")

    return GeminiCvExtractionService(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        api_version=settings.gemini_api_version,
    )
