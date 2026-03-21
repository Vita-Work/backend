import asyncio

from langchain_core.messages import HumanMessage
from src.workflows import build_search_setup_graph
from src.workflows.search_setup.nodes import extraction as extraction_node_module


class FakeGeminiService:
    model = "gemini-test"

    async def extract_from_text(self, *, cv_text: str):
        return type(
            "Result",
            (),
            {
                "extracted_profile": f"profile::{cv_text}",
                "missing_info": ["location"],
                "preference_hints": ["remote-friendly"],
            },
        )()

    async def extract_from_file(self, *, file_path, mime_type: str):
        return type(
            "Result",
            (),
            {
                "extracted_profile": f"profile::{mime_type}",
                "missing_info": ["salary"],
                "preference_hints": ["senior backend"],
            },
        )()


def test_search_setup_graph_runs_extraction_for_local_text(monkeypatch) -> None:
    monkeypatch.setattr(
        extraction_node_module,
        "get_gemini_cv_extraction_service",
        lambda: FakeGeminiService(),
    )
    graph = build_search_setup_graph()

    result = asyncio.run(
        graph.ainvoke(
            {
                "messages": [HumanMessage(content="Start workflow")],
                "status": "ingesting",
                "user_id": "user-1",
                "cv_object_key": "vita/cv/1/resume.txt",
                "cv_object_uri": "s3://bucket/vita/cv/1/resume.txt",
                "cv_filename": "resume.txt",
                "cv_content_type": "text/plain",
                "cv_extension": ".txt",
                "extraction_strategy": "local_text",
                "cv_inline_text": "Senior Backend Engineer\nPython FastAPI",
            }
        )
    )

    assert result["status"] == "clarifying"
    assert result["extracted_profile"] == "profile::Senior Backend Engineer\nPython FastAPI"
    assert result["missing_info"] == ["location"]
    assert result["preference_hints"] == ["remote-friendly"]


def test_search_setup_graph_runs_pdf_path(monkeypatch) -> None:
    class FakeS3Storage:
        async def download_to_path(self, *, key: str, destination) -> object:
            assert key == "vita/cv/1/resume.pdf"
            destination.write_bytes(b"%PDF-1.7 fake")
            return destination

    monkeypatch.setattr(
        extraction_node_module,
        "get_gemini_cv_extraction_service",
        lambda: FakeGeminiService(),
    )
    monkeypatch.setattr(extraction_node_module, "get_s3_storage", lambda: FakeS3Storage())
    graph = build_search_setup_graph()

    result = asyncio.run(
        graph.ainvoke(
            {
                "messages": [HumanMessage(content="Start workflow")],
                "status": "ingesting",
                "user_id": "user-2",
                "cv_object_key": "vita/cv/1/resume.pdf",
                "cv_object_uri": "s3://bucket/vita/cv/1/resume.pdf",
                "cv_filename": "resume.pdf",
                "cv_content_type": "application/pdf",
                "cv_extension": ".pdf",
                "extraction_strategy": "model_file",
            }
        )
    )

    assert result["status"] == "clarifying"
    assert result["extracted_profile"] == "profile::application/pdf"
    assert result["missing_info"] == ["salary"]
    assert result["preference_hints"] == ["senior backend"]
