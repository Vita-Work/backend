from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4

import aioboto3
from aiobotocore.config import AioConfig
from boto3.s3.transfer import TransferConfig
from botocore.exceptions import ClientError

from src.config import get_settings
from src.logger import get_logger

logger = get_logger("storage.s3")


class S3StorageError(RuntimeError):
    """Raised when an S3 operation fails."""


@dataclass(frozen=True, slots=True)
class S3ObjectRef:
    """A stored object reference in an S3-compatible bucket."""

    bucket: str
    key: str
    content_type: str | None = None
    size_bytes: int | None = None
    etag: str | None = None
    version_id: str | None = None

    @property
    def uri(self) -> str:
        """Return the canonical S3 URI for the object."""
        return f"s3://{self.bucket}/{self.key}"


class S3Storage:
    """Async client for working with S3-compatible object storage."""

    def __init__(
        self,
        *,
        endpoint_url: str,
        region_name: str,
        bucket_name: str,
        access_key_id: str,
        secret_access_key: str,
        key_prefix: str = "",
        connect_timeout_seconds: int = 5,
        read_timeout_seconds: int = 30,
        max_pool_connections: int = 50,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.region_name = region_name
        self.bucket_name = bucket_name
        self.key_prefix = key_prefix.strip("/")
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._session = aioboto3.Session()
        self._client_config = AioConfig(
            signature_version="s3v4",
            retries={"max_attempts": 5, "mode": "adaptive"},
            connect_timeout=connect_timeout_seconds,
            read_timeout=read_timeout_seconds,
            max_pool_connections=max_pool_connections,
            s3={"addressing_style": "path"},
        )
        self._transfer_config = TransferConfig(
            multipart_threshold=8 * 1024 * 1024,
            multipart_chunksize=8 * 1024 * 1024,
            max_concurrency=8,
            use_threads=True,
        )

    @asynccontextmanager
    async def client(self) -> AsyncIterator[Any]:
        """Yield a configured async S3 client."""
        async with self._session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            region_name=self.region_name,
            aws_access_key_id=self._access_key_id,
            aws_secret_access_key=self._secret_access_key,
            config=self._client_config,
        ) as client:
            yield client

    def build_object_key(self, *, namespace: str, filename: str) -> str:
        """Build a deterministic path-like key for an uploaded object."""
        now = datetime.now(UTC)
        safe_filename = Path(filename).name.replace(" ", "_")
        path_parts = [
            self.key_prefix,
            namespace.strip("/"),
            now.strftime("%Y"),
            now.strftime("%m"),
            now.strftime("%d"),
            f"{uuid4().hex}_{safe_filename}",
        ]
        return "/".join(part for part in path_parts if part)

    async def upload_path(
        self,
        *,
        path: Path,
        key: str,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> S3ObjectRef:
        """Upload a local file path to object storage and return its stored reference."""
        extra_args: dict[str, Any] = {"ContentType": content_type}
        if metadata:
            extra_args["Metadata"] = metadata

        try:
            async with self.client() as client:
                with path.open("rb") as file_obj:
                    await client.upload_fileobj(
                        file_obj,
                        self.bucket_name,
                        key,
                        ExtraArgs=extra_args,
                        Config=self._transfer_config,
                    )

                head = await client.head_object(Bucket=self.bucket_name, Key=key)
        except ClientError as exc:
            logger.error(
                "s3_upload_failed",
                bucket=self.bucket_name,
                key=key,
                error=str(exc),
                exc_info=True,
            )
            raise S3StorageError(f"Failed to upload object to S3: {key}") from exc

        logger.info(
            "s3_upload_completed",
            bucket=self.bucket_name,
            key=key,
            size_bytes=head.get("ContentLength"),
            content_type=content_type,
        )
        return S3ObjectRef(
            bucket=self.bucket_name,
            key=key,
            content_type=head.get("ContentType"),
            size_bytes=head.get("ContentLength"),
            etag=(head.get("ETag") or "").strip('"') or None,
            version_id=head.get("VersionId"),
        )

    async def download_bytes(self, *, key: str) -> bytes:
        """Download an object into memory."""
        try:
            async with self.client() as client:
                response = await client.get_object(Bucket=self.bucket_name, Key=key)
                async with response["Body"] as stream:
                    return await stream.read()
        except ClientError as exc:
            logger.error(
                "s3_download_failed",
                bucket=self.bucket_name,
                key=key,
                error=str(exc),
                exc_info=True,
            )
            raise S3StorageError(f"Failed to download object from S3: {key}") from exc

    async def download_to_path(self, *, key: str, destination: Path) -> Path:
        """Download an object to a local file path without buffering the whole object in memory."""
        try:
            async with self.client() as client:
                await client.download_file(
                    Bucket=self.bucket_name,
                    Key=key,
                    Filename=str(destination),
                    Config=self._transfer_config,
                )
        except ClientError as exc:
            logger.error(
                "s3_download_to_path_failed",
                bucket=self.bucket_name,
                key=key,
                destination=str(destination),
                error=str(exc),
                exc_info=True,
            )
            raise S3StorageError(f"Failed to download object from S3: {key}") from exc

        logger.info(
            "s3_download_to_path_completed",
            bucket=self.bucket_name,
            key=key,
            destination=str(destination),
        )
        return destination

    async def delete_object(self, *, key: str) -> None:
        """Delete an object from storage."""
        try:
            async with self.client() as client:
                await client.delete_object(Bucket=self.bucket_name, Key=key)
        except ClientError as exc:
            logger.error(
                "s3_delete_failed",
                bucket=self.bucket_name,
                key=key,
                error=str(exc),
                exc_info=True,
            )
            raise S3StorageError(f"Failed to delete object from S3: {key}") from exc


@lru_cache(maxsize=1)
def get_s3_storage() -> S3Storage:
    """Build and cache the shared S3 storage client."""
    settings = get_settings()
    missing_settings = [
        field_name
        for field_name, value in {
            "S3_ENDPOINT_URL": settings.s3_endpoint_url,
            "S3_BUCKET_NAME": settings.s3_bucket_name,
            "S3_ACCESS_KEY_ID": settings.s3_access_key_id,
            "S3_SECRET_ACCESS_KEY": settings.s3_secret_access_key,
        }.items()
        if not value
    ]
    if missing_settings:
        missing = ", ".join(missing_settings)
        raise S3StorageError(f"Missing required S3 settings: {missing}")

    return S3Storage(
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region,
        bucket_name=settings.s3_bucket_name,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key,
        key_prefix=settings.s3_key_prefix,
        connect_timeout_seconds=settings.s3_connect_timeout_seconds,
        read_timeout_seconds=settings.s3_read_timeout_seconds,
        max_pool_connections=settings.s3_max_pool_connections,
    )
