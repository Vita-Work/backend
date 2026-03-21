from __future__ import annotations

import tempfile
from pathlib import Path

from src.extensions.gemini import get_gemini_cv_extraction_service
from src.extensions.s3 import get_s3_storage
from src.logger import get_logger
from src.modules.extraction.parsers import extract_local_cv_text
from src.workflows.search_setup.state import SearchSetupState

logger = get_logger("workflows.search_setup.extraction")


async def extraction_node(state: SearchSetupState) -> dict[str, object]:
    """Prepare the extracted profile context for the first workflow step."""
    strategy = state["extraction_strategy"]
    log = logger.bind(
        user_id=state["user_id"],
        strategy=strategy,
        cv_object_key=state["cv_object_key"],
    )
    log.info("search_setup_extraction_started")

    extraction_service = get_gemini_cv_extraction_service()

    if strategy == "local_text":
        cv_text = state.get("cv_inline_text", "").strip()
        if not cv_text:
            cv_text = await _load_local_text_from_s3(
                cv_object_key=state["cv_object_key"],
                cv_extension=state["cv_extension"],
            )
        extraction_result = await extraction_service.extract_from_text(cv_text=cv_text)
    else:
        extraction_result = await _extract_from_uploaded_file(
            cv_object_key=state["cv_object_key"],
            cv_extension=state["cv_extension"],
            cv_filename=state["cv_filename"],
            cv_content_type=state["cv_content_type"],
        )

    updates: dict[str, object] = {
        "status": "clarifying",
        "extracted_profile": extraction_result.extracted_profile,
        "missing_info": extraction_result.missing_info,
        "preference_hints": extraction_result.preference_hints,
        "extraction_model": extraction_service.model,
    }

    log.info(
        "search_setup_extraction_completed",
        missing_info_count=len(extraction_result.missing_info),
        preference_hints_count=len(extraction_result.preference_hints),
    )
    return updates


async def _load_local_text_from_s3(*, cv_object_key: str, cv_extension: str) -> str:
    storage = get_s3_storage()

    with tempfile.NamedTemporaryFile(suffix=cv_extension, delete=False) as temp_file:
        temp_path = Path(temp_file.name)

    try:
        await storage.download_to_path(key=cv_object_key, destination=temp_path)
        cv_text = await extract_local_cv_text(path=temp_path, extension=cv_extension)
    finally:
        temp_path.unlink(missing_ok=True)

    if not cv_text:
        raise ValueError("Could not reconstruct local CV text from storage.")
    return cv_text


async def _extract_from_uploaded_file(
    *,
    cv_object_key: str,
    cv_extension: str,
    cv_filename: str,
    cv_content_type: str,
):
    storage = get_s3_storage()
    extraction_service = get_gemini_cv_extraction_service()

    with tempfile.NamedTemporaryFile(
        prefix="vita-extraction-",
        suffix=cv_extension or Path(cv_filename).suffix,
        delete=False,
    ) as temp_file:
        temp_path = Path(temp_file.name)

    try:
        await storage.download_to_path(key=cv_object_key, destination=temp_path)
        return await extraction_service.extract_from_file(
            file_path=temp_path,
            mime_type=cv_content_type,
        )
    finally:
        temp_path.unlink(missing_ok=True)
