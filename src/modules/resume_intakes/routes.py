from __future__ import annotations

from datetime import timedelta

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import get_settings
from src.db.engine import get_db_session
from src.extensions.arq.client import get_arq_redis
from src.extensions.gemini import GeminiIntegrationError
from src.extensions.s3 import S3StorageError, get_s3_storage
from src.modules.auth.dependencies import AuthContext, require_authenticated_user
from src.modules.auth.security import (
    generate_resume_intake_token,
    hash_resume_intake_token,
    utcnow,
)
from src.modules.extraction.presenters import build_extraction_workflow_run_response
from src.modules.extraction.schemas import ExtractionInputResponse, StoredCvFileResponse
from src.modules.extraction.use_cases.intake_cv import (
    CvFileTooLargeError,
    InvalidCvFileError,
    PreparedCvExtractionInput,
    UnsupportedCvFileError,
    intake_cv_for_extraction,
)
from src.modules.extraction.use_cases.queue_cv_extraction import (
    WorkflowEnqueueError,
    queue_cv_extraction_workflow,
)
from src.modules.resume_intakes.repository import ResumeIntakesRepository
from src.modules.resume_intakes.schemas import (
    ClaimResumeIntakeRequest,
    CreateResumeIntakeResponse,
    PendingResumeIntakeResponse,
)

settings = get_settings()
upload_file_field = File(...)
db_session_dependency = Depends(get_db_session)
arq_redis_dependency = Depends(get_arq_redis)
user_auth_dependency = Depends(require_authenticated_user)

public_router = APIRouter(prefix="/public", tags=["public"])
me_router = APIRouter(prefix="/me/resume-intakes", tags=["resume-intakes"])


def _build_pending_response(*, intake) -> PendingResumeIntakeResponse:
    return PendingResumeIntakeResponse(
        file=StoredCvFileResponse(
            bucket=intake.storage_bucket,
            key=intake.storage_key,
            uri=intake.storage_uri,
            filename=intake.cv_filename,
            content_type=intake.cv_content_type,
            extension=intake.cv_extension,
            size_bytes=intake.cv_size_bytes,
            sha256=intake.cv_sha256,
        ),
        extraction=ExtractionInputResponse(
            strategy=intake.extraction_strategy,
            inline_text_characters=intake.inline_text_characters,
        ),
        status=intake.status,
        expires_at=intake.expires_at,
        claimed_at=intake.claimed_at,
        created_at=intake.created_at,
    )


def _prepared_cv_from_stored_object(
    *,
    stored_object,
    filename: str,
    extension: str,
    content_type: str,
    size_bytes: int,
    sha256: str,
    extraction_strategy: str,
    inline_text_characters: int | None,
) -> PreparedCvExtractionInput:
    return PreparedCvExtractionInput(
        stored_object=stored_object,
        filename=filename,
        extension=extension,
        content_type=content_type,
        size_bytes=size_bytes,
        sha256=sha256,
        strategy=extraction_strategy,
        inline_text=("x" * inline_text_characters) if inline_text_characters else None,
    )


def _ensure_not_expired(*, intake) -> None:
    now = utcnow()
    if intake.expires_at <= now:
        intake.status = "expired"
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This resume link expired. Please upload your resume again.",
        )


@public_router.post(
    "/resume-intakes",
    response_model=CreateResumeIntakeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_resume_intake_route(
    file: UploadFile = upload_file_field,
    session: AsyncSession = db_session_dependency,
) -> CreateResumeIntakeResponse:
    try:
        prepared_cv = await intake_cv_for_extraction(upload=file, storage_namespace="resume-intake")
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

    raw_token = generate_resume_intake_token()
    intake = ResumeIntakesRepository(session=session).add(
        intake_token_hash=hash_resume_intake_token(raw_token),
        status="uploaded",
        claimed_user_id=None,
        storage_bucket=prepared_cv.stored_object.bucket,
        storage_key=prepared_cv.stored_object.key,
        storage_uri=prepared_cv.stored_object.uri,
        cv_filename=prepared_cv.filename,
        cv_content_type=prepared_cv.content_type,
        cv_extension=prepared_cv.extension,
        cv_size_bytes=prepared_cv.size_bytes,
        cv_sha256=prepared_cv.sha256,
        extraction_strategy=prepared_cv.strategy,
        inline_text_characters=len(prepared_cv.inline_text) if prepared_cv.inline_text else None,
        expires_at=utcnow() + timedelta(hours=settings.resume_intake_ttl_hours),
    )
    await session.commit()
    await session.refresh(intake)

    return CreateResumeIntakeResponse(
        intake_token=raw_token,
        file=StoredCvFileResponse(
            bucket=intake.storage_bucket,
            key=intake.storage_key,
            uri=intake.storage_uri,
            filename=intake.cv_filename,
            content_type=intake.cv_content_type,
            extension=intake.cv_extension,
            size_bytes=intake.cv_size_bytes,
            sha256=intake.cv_sha256,
        ),
        extraction=ExtractionInputResponse(
            strategy=intake.extraction_strategy,
            inline_text_characters=intake.inline_text_characters,
        ),
        status=intake.status,
        expires_at=intake.expires_at,
    )


@me_router.post("/claim", response_model=PendingResumeIntakeResponse)
async def claim_resume_intake_route(
    payload: ClaimResumeIntakeRequest,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> PendingResumeIntakeResponse:
    repository = ResumeIntakesRepository(session=session)
    intake = await repository.get_by_token_hash(
        intake_token_hash=hash_resume_intake_token(payload.intake_token)
    )
    if intake is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume upload not found."
        )

    storage = get_s3_storage()
    try:
        _ensure_not_expired(intake=intake)
    except HTTPException:
        try:
            await storage.delete_object(key=intake.storage_key)
        except S3StorageError:
            pass
        await session.commit()
        raise

    user_id = str(context.user.id)
    if intake.status == "consumed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This resume upload was already used.",
        )
    if intake.claimed_user_id and intake.claimed_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume upload not found."
        )

    intake.claimed_user_id = user_id
    intake.claimed_at = intake.claimed_at or utcnow()
    intake.status = "claimed"
    await session.commit()
    await session.refresh(intake)
    return _build_pending_response(intake=intake)


@me_router.get("/pending", response_model=PendingResumeIntakeResponse | None)
async def get_pending_resume_intake_route(
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> PendingResumeIntakeResponse | None:
    repository = ResumeIntakesRepository(session=session)
    intake = await repository.get_latest_pending_for_user(user_id=str(context.user.id))
    if intake is None:
        return None
    if intake.expires_at <= utcnow():
        intake.status = "expired"
        try:
            await get_s3_storage().delete_object(key=intake.storage_key)
        except S3StorageError:
            pass
        await session.commit()
        return None
    return _build_pending_response(intake=intake)


@me_router.delete("/pending", status_code=status.HTTP_204_NO_CONTENT)
async def discard_pending_resume_intake_route(
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> Response:
    repository = ResumeIntakesRepository(session=session)
    intake = await repository.get_latest_pending_for_user(user_id=str(context.user.id))
    if intake is not None:
        intake.status = "expired"
        try:
            await get_s3_storage().delete_object(key=intake.storage_key)
        except S3StorageError:
            pass
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@me_router.post("/extraction/run", status_code=status.HTTP_202_ACCEPTED)
async def run_pending_resume_extraction_route(
    request: Request,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
    arq_redis: ArqRedis = arq_redis_dependency,
):
    repository = ResumeIntakesRepository(session=session)
    intake = await repository.get_latest_pending_for_user(user_id=str(context.user.id))
    if intake is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending resume is available for onboarding.",
        )
    _ensure_not_expired(intake=intake)

    storage = get_s3_storage()
    target_key = storage.build_object_key(namespace="cv", filename=intake.cv_filename)

    try:
        copied_object = await storage.copy_object(
            source_key=intake.storage_key,
            destination_key=target_key,
            content_type=intake.cv_content_type,
            metadata={
                "sha256": intake.cv_sha256,
                "filename": intake.cv_filename,
                "source": "resume_intake",
            },
        )
        prepared_cv = _prepared_cv_from_stored_object(
            stored_object=copied_object,
            filename=intake.cv_filename,
            extension=intake.cv_extension,
            content_type=intake.cv_content_type,
            size_bytes=intake.cv_size_bytes,
            sha256=intake.cv_sha256,
            extraction_strategy=intake.extraction_strategy,
            inline_text_characters=intake.inline_text_characters,
        )
        workflow_run = await queue_cv_extraction_workflow(
            session=session,
            arq_redis=arq_redis,
            user_id=str(context.user.id),
            prepared_cv=prepared_cv,
            parent_request_id=getattr(request.state, "request_id", None),
        )
    except (S3StorageError, GeminiIntegrationError, WorkflowEnqueueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is temporarily unavailable.",
        ) from exc

    intake.status = "consumed"
    intake.consumed_at = utcnow()
    try:
        await storage.delete_object(key=intake.storage_key)
    except S3StorageError:
        pass
    await session.commit()
    return build_extraction_workflow_run_response(workflow_run=workflow_run)
