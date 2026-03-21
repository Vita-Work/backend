import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from src.workflows.search_setup.nodes import extraction as extraction_node_module


class FakeGeminiService:
    model = "gemini-test"

    def __init__(self) -> None:
        self.text_calls: list[str] = []
        self.file_calls: list[tuple[Path, str]] = []

    async def extract_from_text(self, *, cv_text: str):
        self.text_calls.append(cv_text)
        return SimpleNamespace(
            extracted_profile=f"profile::{cv_text}",
            missing_info=["location"],
            preference_hints=["remote-friendly"],
        )

    async def extract_from_file(self, *, file_path: Path, mime_type: str):
        self.file_calls.append((file_path, mime_type))
        return SimpleNamespace(
            extracted_profile="profile::pdf",
            missing_info=["salary"],
            preference_hints=["senior backend"],
        )


def test_extraction_node_uses_gemini_for_local_text(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_service = FakeGeminiService()

    monkeypatch.setattr(
        extraction_node_module,
        "get_gemini_cv_extraction_service",
        lambda: fake_service,
    )

    result = asyncio.run(
        extraction_node_module.extraction_node(
            {
                "messages": [],
                "status": "ingesting",
                "user_id": "user-1",
                "cv_object_key": "vita/cv/resume.txt",
                "cv_object_uri": "s3://bucket/vita/cv/resume.txt",
                "cv_filename": "resume.txt",
                "cv_content_type": "text/plain",
                "cv_extension": ".txt",
                "extraction_strategy": "local_text",
                "cv_inline_text": "Senior Backend Engineer",
            }
        )
    )

    assert fake_service.text_calls == ["Senior Backend Engineer"]
    assert result["status"] == "clarifying"
    assert result["extracted_profile"] == "profile::Senior Backend Engineer"
    assert result["missing_info"] == ["location"]
    assert result["preference_hints"] == ["remote-friendly"]
    assert result["extraction_model"] == "gemini-test"


def test_extraction_node_uses_file_path_for_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_service = FakeGeminiService()

    class FakeS3Storage:
        async def download_to_path(self, *, key: str, destination: Path) -> Path:
            assert key == "vita/cv/resume.pdf"
            destination.write_bytes(b"%PDF-1.7 fake")
            return destination

    monkeypatch.setattr(
        extraction_node_module,
        "get_gemini_cv_extraction_service",
        lambda: fake_service,
    )
    monkeypatch.setattr(extraction_node_module, "get_s3_storage", lambda: FakeS3Storage())

    result = asyncio.run(
        extraction_node_module.extraction_node(
            {
                "messages": [],
                "status": "ingesting",
                "user_id": "user-2",
                "cv_object_key": "vita/cv/resume.pdf",
                "cv_object_uri": "s3://bucket/vita/cv/resume.pdf",
                "cv_filename": "resume.pdf",
                "cv_content_type": "application/pdf",
                "cv_extension": ".pdf",
                "extraction_strategy": "model_file",
            }
        )
    )

    assert len(fake_service.file_calls) == 1
    uploaded_path, mime_type = fake_service.file_calls[0]
    assert uploaded_path.suffix == ".pdf"
    assert mime_type == "application/pdf"
    assert result["status"] == "clarifying"
    assert result["extracted_profile"] == "profile::pdf"
    assert result["missing_info"] == ["salary"]
    assert result["preference_hints"] == ["senior backend"]
