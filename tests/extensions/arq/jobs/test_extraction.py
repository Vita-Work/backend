import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from src.extensions.arq.jobs import extraction as extraction_job_module
from src.extensions.gemini import GeminiProviderError


class FakeAsyncSession:
    def __init__(self) -> None:
        self.commit_calls = 0

    async def commit(self) -> None:
        self.commit_calls += 1


class FakeRedis:
    def __init__(self) -> None:
        self.deleted_keys: list[tuple[object, ...]] = []
        self.incr_calls: list[str] = []
        self.expire_calls: list[tuple[str, int]] = []
        self.set_calls: list[tuple[str, object, int]] = []

    async def delete(self, *keys):
        self.deleted_keys.append(keys)

    async def incr(self, key: str) -> int:
        self.incr_calls.append(key)
        return 1

    async def expire(self, key: str, ttl_seconds: int) -> None:
        self.expire_calls.append((key, ttl_seconds))

    async def set(self, key: str, value: object, ex: int) -> None:
        self.set_calls.append((key, value, ex))


def test_process_cv_extraction_workflow_persists_result(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeAsyncSession()
    redis = FakeRedis()
    onboarding_session_id = uuid4()
    workflow_run = SimpleNamespace(
        id=uuid4(),
        user_id="user-1",
        onboarding_session_id=onboarding_session_id,
        status="queued",
        error_message=None,
        storage_bucket="bucket",
        storage_key="cv/key.pdf",
        cv_filename="resume.pdf",
        cv_content_type="application/pdf",
        cv_extension=".pdf",
        cv_size_bytes=123,
        cv_sha256="abc123",
        extraction_strategy="model_file",
        extracted_profile=None,
        missing_info=None,
        preference_hints=None,
        extraction_model=None,
    )
    onboarding_session = SimpleNamespace(
        id=onboarding_session_id,
        status="extracting",
        current_step="extraction",
        latest_workflow_run_id=None,
        extracted_profile=None,
        missing_info=None,
        preference_hints=None,
        clarification_turns=None,
        pending_user_prompt=None,
        pending_user_prompt_type=None,
        extraction_model=None,
        last_error_message=None,
    )

    class FakeRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def get_by_id(self, *, workflow_run_id):
            assert workflow_run_id == workflow_run.id
            return workflow_run

    class FakeOnboardingRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def get_by_id(self, *, onboarding_session_id):
            assert onboarding_session_id == onboarding_session.id
            return onboarding_session

    class FakeGraph:
        async def ainvoke(self, graph_input, config, **kwargs):
            assert graph_input["user_id"] == "user-1"
            assert graph_input["onboarding_session_id"] == str(onboarding_session.id)
            assert graph_input["cv_object_key"] == "cv/key.pdf"
            assert config["configurable"]["thread_id"] == str(onboarding_session.id)
            return {
                "__interrupt__": [
                    SimpleNamespace(
                        value={
                            "type": "clarification_question",
                            "prompt": "What work format do you prefer?",
                        }
                    )
                ]
            }

        async def aget_state(self, config):
            assert config["configurable"]["thread_id"] == str(onboarding_session.id)
            return SimpleNamespace(
                values={
                    "status": "awaiting_clarification",
                    "extracted_profile": "profile",
                    "missing_info": ["location"],
                    "preference_hints": ["remote"],
                    "extraction_model": "gemini-test",
                    "clarification_turns": [],
                }
            )

    monkeypatch.setattr(
        extraction_job_module,
        "ExtractionWorkflowRunsRepository",
        FakeRepository,
    )
    monkeypatch.setattr(
        extraction_job_module,
        "OnboardingSessionsRepository",
        FakeOnboardingRepository,
    )
    fake_graph = FakeGraph()

    async def fake_invoke_search_setup_graph(*, graph_input, config, durability="sync"):
        assert durability == "sync"
        return await fake_graph.ainvoke(graph_input, config)

    async def fake_get_search_setup_state(config):
        return await fake_graph.aget_state(config)

    monkeypatch.setattr(extraction_job_module, "get_search_setup_graph", lambda: object())
    monkeypatch.setattr(
        extraction_job_module,
        "invoke_search_setup_graph",
        fake_invoke_search_setup_graph,
    )
    monkeypatch.setattr(
        extraction_job_module,
        "get_search_setup_state",
        fake_get_search_setup_state,
    )

    asyncio.run(
        extraction_job_module.process_cv_extraction_workflow.__wrapped__.__wrapped__(  # type: ignore[attr-defined]
            {"redis": redis},
            str(workflow_run.id),
            session=session,
        )
    )

    assert session.commit_calls == 2
    assert workflow_run.status == "awaiting_clarification"
    assert workflow_run.extracted_profile == "profile"
    assert workflow_run.missing_info == ["location"]
    assert workflow_run.preference_hints == ["remote"]
    assert workflow_run.extraction_model == "gemini-test"
    assert onboarding_session.status == "awaiting_clarification"
    assert onboarding_session.current_step == "clarification"
    assert onboarding_session.latest_workflow_run_id == workflow_run.id
    assert onboarding_session.extracted_profile == "profile"
    assert onboarding_session.missing_info == ["location"]
    assert onboarding_session.preference_hints == ["remote"]
    assert onboarding_session.clarification_turns == []
    assert onboarding_session.pending_user_prompt == "What work format do you prefer?"
    assert onboarding_session.pending_user_prompt_type == "clarification_question"
    assert onboarding_session.extraction_model == "gemini-test"
    assert redis.deleted_keys == [
        (
            "vita:cv_extraction:provider_failure_count",
            "vita:cv_extraction:provider_degraded",
        )
    ]


def test_process_cv_extraction_workflow_marks_failed_phase_with_error_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeAsyncSession()
    redis = FakeRedis()
    workflow_run = SimpleNamespace(
        id=uuid4(),
        user_id="user-1",
        onboarding_session_id=None,
        status="queued",
        error_message=None,
        storage_bucket="bucket",
        storage_key="cv/key.pdf",
        storage_uri="s3://bucket/cv/key.pdf",
        cv_filename="resume.pdf",
        cv_content_type="application/pdf",
        cv_extension=".pdf",
        cv_size_bytes=123,
        cv_sha256="abc123",
        extraction_strategy="model_file",
        extracted_profile=None,
        missing_info=None,
        preference_hints=None,
        extraction_model=None,
    )
    progress_calls: list[dict[str, object | None]] = []

    class FakeRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def get_by_id(self, *, workflow_run_id):
            assert workflow_run_id == workflow_run.id
            return workflow_run

    class FakeOnboardingRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

    async def fake_invoke_search_setup_graph(*, graph_input, config, durability="sync"):
        _ = graph_input
        _ = config
        _ = durability
        raise GeminiProviderError(
            "CV extraction is temporarily unavailable because the provider quota is exhausted.",
            error_code="provider_quota_exhausted",
            retryable=True,
            diagnostic_message="429 RESOURCE_EXHAUSTED",
        )

    def fake_update_extraction_progress(**kwargs):
        progress_calls.append(
            {
                "event_type": kwargs["event_type"],
                "phase": kwargs["phase"],
                "payload": kwargs.get("payload"),
            }
        )

    monkeypatch.setattr(
        extraction_job_module,
        "ExtractionWorkflowRunsRepository",
        FakeRepository,
    )
    monkeypatch.setattr(
        extraction_job_module,
        "OnboardingSessionsRepository",
        FakeOnboardingRepository,
    )
    monkeypatch.setattr(extraction_job_module, "get_search_setup_graph", lambda: object())
    monkeypatch.setattr(
        extraction_job_module,
        "invoke_search_setup_graph",
        fake_invoke_search_setup_graph,
    )
    monkeypatch.setattr(
        extraction_job_module,
        "update_extraction_progress",
        fake_update_extraction_progress,
    )

    with pytest.raises(
        GeminiProviderError,
        match="provider quota is exhausted",
    ):
        asyncio.run(
            extraction_job_module.process_cv_extraction_workflow.__wrapped__.__wrapped__(  # type: ignore[attr-defined]
                {"redis": redis},
                str(workflow_run.id),
                session=session,
            )
        )

    assert session.commit_calls == 2
    assert workflow_run.status == "failed"
    assert workflow_run.error_message == (
        "CV extraction is temporarily unavailable because the provider quota is exhausted."
    )
    assert progress_calls[-1]["phase"] == "failed"
    assert progress_calls[-1]["payload"] == {
        "error_code": "provider_quota_exhausted",
        "retryable": True,
        "error_message": (
            "CV extraction is temporarily unavailable because the provider quota is exhausted."
        ),
        "ui_label": "Extraction failed",
        "ui_description": (
            "The CV processor hit provider limits. Please try again in a few minutes."
        ),
    }
    assert redis.incr_calls == ["vita:cv_extraction:provider_failure_count"]
