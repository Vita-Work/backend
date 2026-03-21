from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    environment: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_name: str = "Vita Backend"
    app_version: str = "0.1.0"
    connection_string: str | None = None
    service_name: str = "vita-backend"
    log_level: str | None = None
    log_format: Literal["console", "json"] | None = None
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None
    arq_max_jobs: int = 50
    arq_job_timeout: int = 300
    arq_keep_result: int = 3600
    s3_endpoint_url: str | None = None
    s3_region: str = "auto"
    s3_bucket_name: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_key_prefix: str = "vita"
    s3_connect_timeout_seconds: int = 5
    s3_read_timeout_seconds: int = 30
    s3_max_pool_connections: int = 50
    cv_upload_max_size_mb: int = 30
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_api_version: str = "v1alpha"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cv_upload_max_size_bytes(self) -> int:
        """Return the configured CV upload size limit in bytes."""
        return self.cv_upload_max_size_mb * 1024 * 1024

    @property
    def effective_log_level(self) -> str:
        """Return the effective log level based on explicit config or environment."""
        if self.log_level:
            return self.log_level

        return {
            "local": "DEBUG",
            "development": "DEBUG",
            "staging": "DEBUG",
            "production": "INFO",
        }.get(self.environment, "INFO")

    @property
    def effective_log_format(self) -> Literal["console", "json"]:
        """Return the effective log format based on explicit config or environment."""
        if self.log_format:
            return self.log_format

        return "console" if self.environment == "local" else "json"


def get_settings() -> Settings:
    """Build and return application settings."""
    return Settings()
