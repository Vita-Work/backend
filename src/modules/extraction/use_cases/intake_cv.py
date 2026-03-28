from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from src.config import get_settings
from src.extensions.s3 import S3ObjectRef, S3Storage, get_s3_storage
from src.logger import get_logger
from src.modules.extraction.parsers import extract_local_cv_text, validate_file_signature

logger = get_logger("extraction.intake")

CHUNK_SIZE = 1024 * 1024
SUPPORTED_EXTENSIONS: dict[str, set[str]] = {
    ".pdf": {"application/pdf", "binary/octet-stream", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        "application/octet-stream",
    },
    ".txt": {"text/plain", "application/octet-stream"},
    ".md": {"text/markdown", "text/plain", "application/octet-stream"},
}


class CvIntakeError(Exception):
    """Base exception for CV intake errors."""


class CvFileTooLargeError(CvIntakeError):
    """Raised when the uploaded CV exceeds the configured size limit."""


class UnsupportedCvFileError(CvIntakeError):
    """Raised when the uploaded CV format is not supported."""


class InvalidCvFileError(CvIntakeError):
    """Raised when the uploaded file contents do not match the declared format."""


@dataclass(frozen=True, slots=True)
class PreparedCvExtractionInput:
    """Prepared CV payload for downstream extraction."""

    stored_object: S3ObjectRef
    filename: str
    extension: str
    content_type: str
    size_bytes: int
    sha256: str
    strategy: str
    inline_text: str | None


@dataclass(frozen=True, slots=True)
class _BufferedUpload:
    path: Path
    filename: str
    extension: str
    content_type: str
    size_bytes: int
    sha256: str


def _normalize_filename(filename: str | None) -> str:
    candidate = Path(filename or "cv_upload").name.strip()
    return candidate or "cv_upload"


def _resolve_extension(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise UnsupportedCvFileError(
            "Unsupported CV format. Supported formats: pdf, docx, txt, md."
        )
    return extension


def _resolve_content_type(*, extension: str, upload_content_type: str | None) -> str:
    normalized_content_type = (upload_content_type or "application/octet-stream").lower()
    allowed_types = SUPPORTED_EXTENSIONS[extension]
    if normalized_content_type not in allowed_types:
        raise UnsupportedCvFileError(
            f"Unsupported content type '{normalized_content_type}' for {extension} file."
        )

    if normalized_content_type == "binary/octet-stream":
        return "application/octet-stream"
    return normalized_content_type


def _resolve_strategy(extension: str) -> str:
    if extension == ".pdf":
        return "model_file"
    return "local_text"


async def _buffer_upload_to_disk(upload: UploadFile, *, max_size_bytes: int) -> _BufferedUpload:
    filename = _normalize_filename(upload.filename)
    extension = _resolve_extension(filename)
    content_type = _resolve_content_type(
        extension=extension,
        upload_content_type=upload.content_type,
    )

    file_hash = hashlib.sha256()
    total_size = 0
    temp_file = tempfile.NamedTemporaryFile(prefix="vita-cv-", suffix=extension, delete=False)
    temp_path = Path(temp_file.name)

    try:
        while chunk := await upload.read(CHUNK_SIZE):
            total_size += len(chunk)
            if total_size > max_size_bytes:
                raise CvFileTooLargeError("Uploaded CV exceeds the configured size limit.")

            file_hash.update(chunk)
            temp_file.write(chunk)
    except Exception:
        temp_file.close()
        temp_path.unlink(missing_ok=True)
        raise
    else:
        temp_file.flush()
        os.fsync(temp_file.fileno())
        temp_file.close()

    return _BufferedUpload(
        path=temp_path,
        filename=filename,
        extension=extension,
        content_type=content_type,
        size_bytes=total_size,
        sha256=file_hash.hexdigest(),
    )


async def intake_cv_for_extraction(
    *,
    upload: UploadFile,
    s3_storage: S3Storage | None = None,
    storage_namespace: str = "cv",
) -> PreparedCvExtractionInput:
    """Persist a CV upload and prepare the next extraction input."""
    settings = get_settings()
    storage = s3_storage or get_s3_storage()

    try:
        buffered_upload = await _buffer_upload_to_disk(
            upload,
            max_size_bytes=settings.cv_upload_max_size_bytes,
        )

        try:
            try:
                validate_file_signature(
                    path=buffered_upload.path,
                    extension=buffered_upload.extension,
                )
            except ValueError as exc:
                raise InvalidCvFileError(str(exc)) from exc

            try:
                inline_text = await extract_local_cv_text(
                    path=buffered_upload.path,
                    extension=buffered_upload.extension,
                )
            except Exception as exc:
                logger.warning(
                    "cv_local_text_extraction_failed",
                    filename=buffered_upload.filename,
                    extension=buffered_upload.extension,
                    error=str(exc),
                    exc_info=True,
                )
                raise InvalidCvFileError("Uploaded CV could not be parsed.") from exc
            strategy = _resolve_strategy(buffered_upload.extension)

            object_key = storage.build_object_key(
                namespace=storage_namespace,
                filename=buffered_upload.filename,
            )
            stored_object = await storage.upload_path(
                path=buffered_upload.path,
                key=object_key,
                content_type=buffered_upload.content_type,
                metadata={
                    "sha256": buffered_upload.sha256,
                    "filename": buffered_upload.filename,
                    "source": "cv_upload",
                },
            )
        finally:
            buffered_upload.path.unlink(missing_ok=True)
    finally:
        await upload.close()

    logger.info(
        "cv_intake_completed",
        filename=buffered_upload.filename,
        extension=buffered_upload.extension,
        strategy=strategy,
        size_bytes=buffered_upload.size_bytes,
        storage_key=stored_object.key,
    )
    return PreparedCvExtractionInput(
        stored_object=stored_object,
        filename=buffered_upload.filename,
        extension=buffered_upload.extension,
        content_type=buffered_upload.content_type,
        size_bytes=buffered_upload.size_bytes,
        sha256=buffered_upload.sha256,
        strategy=strategy,
        inline_text=inline_text,
    )
