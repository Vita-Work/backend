from __future__ import annotations

from dataclasses import dataclass

from src.extensions.gemini import GeminiIntegrationError, GeminiProviderError
from src.extensions.s3 import S3StorageError


@dataclass(frozen=True, slots=True)
class ExtractionFailureDetails:
    error_code: str
    error_message: str
    ui_label: str
    ui_description: str
    retryable: bool


def describe_extraction_failure(*, exc: Exception) -> ExtractionFailureDetails:
    """Map runtime failures into stable frontend-safe extraction errors."""
    if isinstance(exc, GeminiProviderError):
        return ExtractionFailureDetails(
            error_code=exc.error_code,
            error_message=str(exc),
            ui_label="Extraction failed",
            ui_description=_description_for_error_code(exc.error_code),
            retryable=exc.retryable,
        )

    if isinstance(exc, S3StorageError):
        return ExtractionFailureDetails(
            error_code="storage_unavailable",
            error_message="CV extraction could not access the stored file.",
            ui_label="Storage unavailable",
            ui_description="We could not access your CV file. Please retry in a moment.",
            retryable=True,
        )

    if isinstance(exc, GeminiIntegrationError):
        return ExtractionFailureDetails(
            error_code="provider_request_failed",
            error_message="CV extraction could not complete with the AI provider.",
            ui_label="Extraction unavailable",
            ui_description="The CV processor is unavailable right now. Please try again later.",
            retryable=False,
        )

    return ExtractionFailureDetails(
        error_code="internal_error",
        error_message="CV extraction stopped because of an unexpected internal error.",
        ui_label="Extraction failed",
        ui_description="Something unexpected interrupted CV extraction.",
        retryable=False,
    )


def build_enqueue_failure_details() -> ExtractionFailureDetails:
    """Return the stable failure contract for workflow queueing problems."""
    return ExtractionFailureDetails(
        error_code="enqueue_failed",
        error_message="CV extraction could not be queued.",
        ui_label="Queueing failed",
        ui_description="We could not start CV extraction right now. Please retry.",
        retryable=True,
    )


def _description_for_error_code(error_code: str) -> str:
    if error_code == "provider_quota_exhausted":
        return "The CV processor hit provider limits. Please try again in a few minutes."
    if error_code == "provider_timeout":
        return "The CV processor timed out before it could finish. Please retry."
    if error_code == "provider_invalid_response":
        return "The CV processor returned an invalid result. Please retry your extraction."
    if error_code == "provider_unavailable":
        return "The CV processor is temporarily unavailable. Please retry shortly."
    if error_code == "provider_request_failed":
        return "The CV processor could not complete the request. Please retry later."
    return "Something interrupted CV extraction and needs attention."
