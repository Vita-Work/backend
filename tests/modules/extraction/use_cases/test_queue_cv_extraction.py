import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from src.modules.extraction.use_cases import queue_cv_extraction as queue_module


class FakeAsyncSession:
    def __init__(self) -> None:
        self.commit_calls = 0
        self.refresh_calls: list[object] = []
        self.flush_calls = 0

    async def commit(self) -> None:
        self.commit_calls += 1

    async def refresh(self, instance: object) -> None:
        self.refresh_calls.append(instance)

    async def flush(self) -> None:
        self.flush_calls += 1


def test_queue_cv_extraction_persists_and_enqueues(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeAsyncSession()
    workflow_run = SimpleNamespace(id=uuid4(), status="queued")
    onboarding_session = SimpleNamespace(
        id=uuid4(),
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
    repository_state: dict[str, object] = {}
    onboarding_repository_state: dict[str, object] = {}
    redis_calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    class FakeRepository:
        def __init__(self, *, session: object) -> None:
            repository_state["session"] = session

        def add(self, **kwargs):
            repository_state["payload"] = kwargs
            return workflow_run

    class FakeOnboardingRepository:
        def __init__(self, *, session: object) -> None:
            onboarding_repository_state["session"] = session

        async def get_active_for_user(self, *, user_id: str):
            onboarding_repository_state["active_user_id"] = user_id
            return None

        def add(self, **kwargs):
            onboarding_repository_state["payload"] = kwargs
            return onboarding_session

    class FakeRedis:
        async def enqueue_job(self, function: str, *args, **kwargs):
            redis_calls.append((function, args, kwargs))
            return object()

    prepared_cv = SimpleNamespace(
        stored_object=SimpleNamespace(
            bucket="bucket", key="cv/key.pdf", uri="s3://bucket/cv/key.pdf"
        ),
        filename="resume.pdf",
        content_type="application/pdf",
        extension=".pdf",
        size_bytes=123,
        sha256="abc123",
        strategy="model_file",
        inline_text=None,
    )

    monkeypatch.setattr(queue_module, "ExtractionWorkflowRunsRepository", FakeRepository)
    monkeypatch.setattr(queue_module, "OnboardingSessionsRepository", FakeOnboardingRepository)

    result = asyncio.run(
        queue_module.queue_cv_extraction_workflow(
            session=session,
            arq_redis=FakeRedis(),
            user_id="user-1",
            prepared_cv=prepared_cv,
            parent_request_id="req-1",
        )
    )

    assert result is workflow_run
    assert repository_state["session"] is session
    assert onboarding_repository_state["session"] is session
    assert onboarding_repository_state["active_user_id"] == "user-1"
    assert onboarding_repository_state["payload"] == {
        "user_id": "user-1",
        "status": "extracting",
        "current_step": "extraction",
    }
    assert repository_state["payload"] == {
        "user_id": "user-1",
        "onboarding_session_id": onboarding_session.id,
        "status": "queued",
        "storage_bucket": "bucket",
        "storage_key": "cv/key.pdf",
        "storage_uri": "s3://bucket/cv/key.pdf",
        "cv_filename": "resume.pdf",
        "cv_content_type": "application/pdf",
        "cv_extension": ".pdf",
        "cv_size_bytes": 123,
        "cv_sha256": "abc123",
        "extraction_strategy": "model_file",
        "inline_text_characters": None,
    }
    assert onboarding_session.latest_workflow_run_id == workflow_run.id
    assert session.flush_calls == 2
    assert session.commit_calls == 1
    assert session.refresh_calls == [workflow_run]
    assert len(redis_calls) == 1
    function, args, kwargs = redis_calls[0]
    assert function == "process_cv_extraction_workflow"
    assert args == (str(workflow_run.id),)
    assert kwargs["_job_id"] == str(workflow_run.id)
    assert kwargs["_parent_request_id"] == "req-1"
    assert kwargs["_user_id"] == "user-1"
