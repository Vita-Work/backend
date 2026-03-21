from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import HumanMessage

from src.logger import get_logger
from src.modules.extraction.use_cases.intake_cv import PreparedCvExtractionInput
from src.workflows import build_search_setup_graph

logger = get_logger("extraction.workflow")


@dataclass(frozen=True, slots=True)
class CompletedCvExtraction:
    """Completed extraction workflow output."""

    status: str
    extracted_profile: str
    missing_info: list[str]
    preference_hints: list[str]
    extraction_model: str | None


async def run_cv_extraction_workflow(
    *,
    user_id: str,
    prepared_cv: PreparedCvExtractionInput,
) -> CompletedCvExtraction:
    """Run the search-setup extraction workflow for a prepared CV input."""
    graph = build_search_setup_graph()
    logger.info(
        "cv_extraction_workflow_started",
        user_id=user_id,
        strategy=prepared_cv.strategy,
        storage_key=prepared_cv.stored_object.key,
    )
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="Extract a candidate profile from the uploaded CV.")],
            "status": "ingesting",
            "user_id": user_id,
            "cv_object_key": prepared_cv.stored_object.key,
            "cv_object_uri": prepared_cv.stored_object.uri,
            "cv_filename": prepared_cv.filename,
            "cv_content_type": prepared_cv.content_type,
            "cv_extension": prepared_cv.extension,
            "extraction_strategy": prepared_cv.strategy,
            "cv_inline_text": prepared_cv.inline_text,
        }
    )
    logger.info(
        "cv_extraction_workflow_completed",
        user_id=user_id,
        status=result["status"],
        missing_info_count=len(result.get("missing_info", [])),
        preference_hints_count=len(result.get("preference_hints", [])),
    )
    return CompletedCvExtraction(
        status=result["status"],
        extracted_profile=result["extracted_profile"],
        missing_info=result.get("missing_info", []),
        preference_hints=result.get("preference_hints", []),
        extraction_model=result.get("extraction_model"),
    )
