from uuid import UUID

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_db_session
from src.extensions.arq.client import get_arq_redis
from src.extensions.gemini import GeminiIntegrationError
from src.extensions.s3 import S3StorageError
from src.modules.auth.dependencies import AuthContext, require_admin
from src.modules.extraction.models import ExtractionWorkflowRun
from src.modules.extraction.schemas import (
    CvExtractionWorkflowRunResponse,
    CvUploadResponse,
    ExtractionInputResponse,
    StoredCvFileResponse,
)
from src.modules.extraction.use_cases.get_cv_extraction_run import get_cv_extraction_workflow_run
from src.modules.extraction.use_cases.intake_cv import (
    CvFileTooLargeError,
    InvalidCvFileError,
    UnsupportedCvFileError,
    intake_cv_for_extraction,
)
from src.modules.extraction.use_cases.queue_cv_extraction import (
    WorkflowEnqueueError,
    queue_cv_extraction_workflow,
)

router = APIRouter(prefix="/extraction", tags=["extraction"])
upload_file_field = File(...)
user_id_form = Form(...)
db_session_dependency = Depends(get_db_session)
arq_redis_dependency = Depends(get_arq_redis)
admin_dependency = Depends(require_admin)


def _build_workflow_run_response(
    *,
    workflow_run: ExtractionWorkflowRun,
) -> CvExtractionWorkflowRunResponse:
    return CvExtractionWorkflowRunResponse(
        workflow_run_id=workflow_run.id,
        file=StoredCvFileResponse(
            bucket=workflow_run.storage_bucket,
            key=workflow_run.storage_key,
            uri=workflow_run.storage_uri,
            filename=workflow_run.cv_filename,
            content_type=workflow_run.cv_content_type,
            extension=workflow_run.cv_extension,
            size_bytes=workflow_run.cv_size_bytes,
            sha256=workflow_run.cv_sha256,
        ),
        extraction=ExtractionInputResponse(
            strategy=workflow_run.extraction_strategy,
            inline_text_characters=workflow_run.inline_text_characters,
        ),
        status=workflow_run.status,
        extracted_profile=workflow_run.extracted_profile,
        missing_info=workflow_run.missing_info or [],
        preference_hints=workflow_run.preference_hints or [],
        extraction_model=workflow_run.extraction_model,
        error_message=workflow_run.error_message,
        created_at=workflow_run.created_at,
        updated_at=workflow_run.updated_at,
    )


@router.post("/cv", response_model=CvUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_cv_for_extraction(
    file: UploadFile = upload_file_field,
    _: AuthContext = admin_dependency,
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
    response_model=CvExtractionWorkflowRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_cv_and_run_extraction(
    request: Request,
    user_id: str = user_id_form,
    file: UploadFile = upload_file_field,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
    arq_redis: ArqRedis = arq_redis_dependency,
) -> CvExtractionWorkflowRunResponse:
    """Accept a CV upload and queue the extraction workflow."""
    try:
        prepared_cv = await intake_cv_for_extraction(upload=file)
        workflow_run = await queue_cv_extraction_workflow(
            session=session,
            arq_redis=arq_redis,
            user_id=user_id,
            prepared_cv=prepared_cv,
            parent_request_id=getattr(request.state, "request_id", None),
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
    except (S3StorageError, GeminiIntegrationError, WorkflowEnqueueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return _build_workflow_run_response(workflow_run=workflow_run)


@router.get("/cv/run/{workflow_run_id}", response_model=CvExtractionWorkflowRunResponse)
async def get_cv_extraction_run(
    workflow_run_id: UUID,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> CvExtractionWorkflowRunResponse:
    """Return the current state of an extraction workflow run."""
    workflow_run = await get_cv_extraction_workflow_run(
        session=session,
        workflow_run_id=workflow_run_id,
    )
    if workflow_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found.")

    return _build_workflow_run_response(workflow_run=workflow_run)
