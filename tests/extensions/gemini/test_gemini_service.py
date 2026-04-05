import asyncio
from types import SimpleNamespace

import pytest
from src.extensions.gemini.gemini import (
    GeminiCvExtractionService,
    GeminiIntegrationError,
    GeminiJobSearchService,
    GeminiProviderError,
)


def test_parse_response_wraps_validation_errors() -> None:
    service = GeminiCvExtractionService(
        api_key="test-key",
        model="gemini-test",
    )

    response = SimpleNamespace(parsed={"missing_info": []}, text=None)

    with pytest.raises(GeminiIntegrationError, match="invalid response from the provider"):
        service._parse_response(response=response)


def test_extract_from_text_retries_transient_provider_timeout(monkeypatch) -> None:
    calls = {"count": 0}

    class FakeResponse:
        parsed = {
            "extracted_profile": "profile",
            "missing_info": [],
            "preference_hints": [],
        }
        text = None

    class FakeModels:
        async def generate_content(self, **kwargs):
            _ = kwargs
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("504 DEADLINE_EXCEEDED")
            return FakeResponse()

    class FakeAioClient:
        def __init__(self, **kwargs):
            _ = kwargs
            self.models = FakeModels()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            _ = exc_type
            _ = exc
            _ = tb
            return False

    class FakeClient:
        def __init__(self, **kwargs):
            _ = kwargs
            self.aio = FakeAioClient()

    monkeypatch.setattr("src.extensions.gemini.gemini.genai.Client", FakeClient)
    monkeypatch.setattr("src.extensions.gemini.gemini.asyncio.sleep", lambda _: _async_noop())

    service = GeminiCvExtractionService(api_key="test-key", model="gemini-test")

    result = asyncio.run(service.extract_from_text(cv_text="plain cv text"))

    assert result.extracted_profile == "profile"
    assert calls["count"] == 2


def test_provider_error_from_exception_maps_quota_failures() -> None:
    provider_error = GeminiCvExtractionService._provider_error_from_exception(
        RuntimeError("429 RESOURCE_EXHAUSTED")
    )

    assert isinstance(provider_error, GeminiProviderError)
    assert provider_error.error_code == "provider_quota_exhausted"
    assert provider_error.retryable is True


def test_unify_jobs_batch_retries_transient_provider_timeout(monkeypatch) -> None:
    calls = {"count": 0}

    class FakeResponse:
        parsed = {"jobs": [], "notes": ["ok"]}
        text = None

    class FakeModels:
        async def generate_content(self, **kwargs):
            _ = kwargs
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("504 DEADLINE_EXCEEDED")
            return FakeResponse()

    class FakeAioClient:
        def __init__(self, **kwargs):
            _ = kwargs
            self.models = FakeModels()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            _ = exc_type
            _ = exc
            _ = tb
            return False

    class FakeClient:
        def __init__(self, **kwargs):
            _ = kwargs
            self.aio = FakeAioClient()

    monkeypatch.setattr("src.extensions.gemini.gemini.genai.Client", FakeClient)
    monkeypatch.setattr("src.extensions.gemini.gemini.asyncio.sleep", lambda _: _async_noop())

    service = GeminiJobSearchService(api_key="test-key", model="gemini-test")

    result = asyncio.run(
        service.unify_jobs_batch(
            search_strategy_summary="Focus on ML roles.",
            hard_preferences=["remote"],
            soft_preferences=["product"],
            batch_jobs=[],
        )
    )

    assert result.notes == ["ok"]
    assert calls["count"] == 2


def test_sanitize_batch_job_removes_raw_meta_and_truncates_payload() -> None:
    job = {
        "site": "indeed",
        "job_url": "https://example.com/job",
        "description": "x" * 5000,
        "company_about": "y" * 5000,
        "skills": [f"skill-{index}" for index in range(30)],
        "company_contacts": [f"contact-{index}" for index in range(10)],
        "raw_meta": {"foo": "bar"},
    }

    sanitized = GeminiJobSearchService._sanitize_batch_job(job)

    assert "raw_meta" not in sanitized
    assert len(sanitized["description"]) == 4000
    assert len(sanitized["company_about"]) == 4000
    assert len(sanitized["skills"]) == 20
    assert len(sanitized["company_contacts"]) == 5


async def _async_noop():
    return None
