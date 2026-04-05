from __future__ import annotations

from typing import Literal

from pydantic import model_validator
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
    redis_conn_timeout_seconds: int = 5
    redis_conn_retries: int = 10
    redis_conn_retry_delay_seconds: int = 2
    redis_max_connections: int | None = 100
    redis_retry_on_timeout: bool = True
    arq_max_jobs: int = 50
    arq_max_tries: int = 1
    arq_job_timeout: int = 600
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
    cv_upload_max_size_mb: int = 20
    clarification_max_rounds: int = 5
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_api_version: str = "v1alpha"
    gemini_request_timeout_seconds: int = 180
    gemini_max_retries: int = 2
    cv_extraction_provider_failure_threshold: int = 3
    cv_extraction_provider_failure_window_seconds: int = 300
    cv_extraction_provider_cooldown_seconds: int = 300
    dspy_model: str | None = None
    job_parser_site_concurrency: int = 4
    job_parser_detail_concurrency: int = 8
    indeed_playwright_mode: Literal["headless", "headed", "auto"] = "auto"
    search_job_plan_max_queries: int = 5
    search_job_listing_max_pages: int = 2
    search_job_listing_max_items: int = 12
    search_job_detail_max_jobs: int = 24
    search_job_unified_max_jobs: int = 100
    search_job_unified_batch_size: int = 10
    search_job_monitoring_max_stale_pages_per_query: int = 1
    search_job_listing_embedding_similarity_threshold: float = 0.95
    search_job_detail_embedding_similarity_threshold: float = 0.93
    search_job_embedding_output_dimensionality: int = 128
    search_job_embedding_top_k: int = 5

    admins: str = "{}"
    auth_secret_key: str = "dev-auth-secret-change-me"
    auth_cookie_name_user: str = "vita_user_session"
    auth_cookie_name_admin: str = "vita_admin_session"
    auth_session_ttl_days: int = 30
    auth_email_otp_ttl_minutes: int = 10
    auth_email_otp_length: int = 6
    auth_email_otp_max_attempts: int = 5
    auth_email_resend_cooldown_seconds: int = 60
    auth_email_requests_per_hour: int = 5
    auth_session_touch_interval_seconds: int = 300
    app_base_url: str = "http://localhost:8080"
    resend_api_key: str | None = None
    resend_from_email: str | None = None
    resend_reply_to: str | None = None
    paddle_environment: Literal["sandbox", "production"] = "sandbox"
    paddle_client_side_token: str | None = None
    paddle_product_id_pro: str | None = None
    paddle_price_id_pro_monthly: str | None = None
    paddle_product_id_pro_search: str | None = None
    paddle_price_id_pro_search_monthly: str | None = None
    paddle_product_id_weekly_sprint: str | None = None
    paddle_price_id_weekly_sprint: str | None = None
    paddle_product_id_tailor_pack: str | None = None
    paddle_price_id_tailor_pack_topup: str | None = None
    paddle_webhook_secret: str | None = None
    paddle_webhook_tolerance_seconds: int = 300
    allow_paddle_sandbox_in_production: bool = False
    billing_free_job_limit: int = 3
    billing_free_match_gap_limit: int = 2
    billing_pro_search_included_job_pack_credits: int = 3
    billing_weekly_sprint_included_job_pack_credits: int = 2
    billing_tailor_pack_topup_credits: int = 5
    resume_intake_ttl_hours: int = 24

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def validate_runtime_configuration(self) -> Settings:
        """Reject unsafe production billing defaults unless explicitly overridden."""
        if (
            self.environment.lower() == "production"
            and self.paddle_environment == "sandbox"
            and not self.allow_paddle_sandbox_in_production
        ):
            raise ValueError(
                "PADDLE_ENVIRONMENT=sandbox is not allowed when ENVIRONMENT=production "
                "unless ALLOW_PADDLE_SANDBOX_IN_PRODUCTION=true."
            )
        return self

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

    @property
    def auth_cookie_secure(self) -> bool:
        return self.environment not in {"local", "development"}


def get_settings() -> Settings:
    """Build and return application settings."""
    return Settings()
