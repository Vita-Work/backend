from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from src.extensions.gemini import GeminiIntegrationError
from src.extensions.s3 import S3StorageError
from src.modules.extraction.schemas import (
    CvExtractionWorkflowResponse,
    CvUploadResponse,
    ExtractionInputResponse,
    StoredCvFileResponse,
)
from src.modules.extraction.use_cases.intake_cv import (
    CvFileTooLargeError,
    InvalidCvFileError,
    UnsupportedCvFileError,
    intake_cv_for_extraction,
)
from src.modules.extraction.use_cases.run_cv_extraction import run_cv_extraction_workflow

router = APIRouter(prefix="/extraction", tags=["extraction"])
upload_file_field = File(...)
user_id_form = Form(...)


@router.post("/cv", response_model=CvUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_cv_for_extraction(
    file: UploadFile = upload_file_field,
) -> CvUploadResponse:
    """Accept a CV upload, store the original file, and prepare extraction input."""
    try:
        prepared_cv = await intake_cv_for_extraction(upload=file)
    except CvFileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc
    except UnsupportedCvFileError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
        ) from exc
    except InvalidCvFileError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except S3StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    return CvUploadResponse(
        file=StoredCvFileResponse(
            bucket=prepared_cv.stored_object.bucket,
            key=prepared_cv.stored_object.key,
            uri=prepared_cv.stored_object.uri,
            filename=prepared_cv.filename,
            content_type=prepared_cv.content_type,
            extension=prepared_cv.extension,
            size_bytes=prepared_cv.size_bytes,
            sha256=prepared_cv.sha256,
        ),
        extraction=ExtractionInputResponse(
            strategy=prepared_cv.strategy,
            inline_text_characters=len(prepared_cv.inline_text)
            if prepared_cv.inline_text
            else None,
        ),
    )


@router.post(
    "/cv/run",
    response_model=CvExtractionWorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_cv_and_run_extraction(
    user_id: str = user_id_form,
    file: UploadFile = upload_file_field,
) -> CvExtractionWorkflowResponse:
    """Accept a CV upload and run the extraction workflow end-to-end."""
    try:
        prepared_cv = await intake_cv_for_extraction(upload=file)
        completed_extraction = await run_cv_extraction_workflow(
            user_id=user_id,
            prepared_cv=prepared_cv,
        )
    except CvFileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc
    except UnsupportedCvFileError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
        ) from exc
    except InvalidCvFileError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (S3StorageError, GeminiIntegrationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return CvExtractionWorkflowResponse(
        file=StoredCvFileResponse(
            bucket=prepared_cv.stored_object.bucket,
            key=prepared_cv.stored_object.key,
            uri=prepared_cv.stored_object.uri,
            filename=prepared_cv.filename,
            content_type=prepared_cv.content_type,
            extension=prepared_cv.extension,
            size_bytes=prepared_cv.size_bytes,
            sha256=prepared_cv.sha256,
        ),
        extraction=ExtractionInputResponse(
            strategy=prepared_cv.strategy,
            inline_text_characters=len(prepared_cv.inline_text)
            if prepared_cv.inline_text
            else None,
        ),
        status=completed_extraction.status,
        extracted_profile=completed_extraction.extracted_profile,
        missing_info=completed_extraction.missing_info,
        preference_hints=completed_extraction.preference_hints,
        extraction_model=completed_extraction.extraction_model,
    )
