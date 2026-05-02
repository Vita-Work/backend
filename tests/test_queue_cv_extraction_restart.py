import asyncio
from types import SimpleNamespace
from uuid import uuid4

from src.extensions.s3 import S3ObjectRef
from src.modules.extraction.use_cases import queue_cv_extraction as queue_module
from src.modules.extraction.use_cases.intake_cv import PreparedCvExtractionInput


class FakeSession:
    def __init__(self) -> None:
        self.active_session = SimpleNamespace(
            id=uuid4(),
            status="awaiting_confirmation",
            current_step="confirmation",
            superseded_by_session_id=None,
        )
        self.pending_replacement = None

    async def flush(self) -> None:
        if self.pending_replacement is not None and self.active_session.status != "superseded":
            raise AssertionError(
                "replacement session inserted before old active session was superseded"
            )

    async def commit(self) -> None:
        return None

    async def refresh(self, instance) -> None:
        return None


class FakeOnboardingRepository:
    def __init__(self, *, session: FakeSession) -> None:
        self.session = session

    async def list_active_for_user(self, *, user_id: str):
        return [self.session.active_session]

    async def get_active_for_user(self, *, user_id: str):
        return self.session.active_session

    def add(self, *, user_id: str, status: str, current_step: str, superseded_by_session_id=None):
        replacement = SimpleNamespace(
            id=uuid4(),
            user_id=user_id,
            status=status,
            current_step=current_step,
            superseded_by_session_id=superseded_by_session_id,
            latest_workflow_run_id=None,
        )
        self.session.pending_replacement = replacement
        return replacement


class FakeExtractionRepository:
    def __init__(self, *, session: FakeSession) -> None:
        self.session = session

    def add(self, **kwargs):
        return SimpleNamespace(id=uuid4(), user_id=kwargs["user_id"], status=kwargs["status"])


class FakeRedis:
    async def enqueue_job(self, *args, **kwargs):
        return object()


def test_queue_cv_extraction_supersedes_existing_active_session_before_replacement(
    monkeypatch,
) -> None:
    session = FakeSession()

    monkeypatch.setattr(queue_module, "OnboardingSessionsRepository", FakeOnboardingRepository)
    monkeypatch.setattr(queue_module, "ExtractionWorkflowRunsRepository", FakeExtractionRepository)
    monkeypatch.setattr(queue_module, "update_extraction_progress", lambda **kwargs: None)

    prepared = PreparedCvExtractionInput(
        stored_object=S3ObjectRef(
            bucket="test",
            key="cv/test.pdf",
            content_type="application/pdf",
            size_bytes=1234,
        ),
        filename="test.pdf",
        extension=".pdf",
        content_type="application/pdf",
        size_bytes=1234,
        sha256="abc",
        strategy="model_file",
        inline_text="hello",
    )

    workflow_run = asyncio.run(
        queue_module.queue_cv_extraction_workflow(
            session=session,
            arq_redis=FakeRedis(),
            user_id="user-123",
            prepared_cv=prepared,
        )
    )

    assert session.active_session.status == "superseded"
    assert session.active_session.superseded_by_session_id == session.pending_replacement.id
    assert session.pending_replacement.status == "extracting"
    assert workflow_run.status == "queued"
