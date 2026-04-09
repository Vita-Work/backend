import pytest
from pydantic import ValidationError
from src.config import Settings


def test_settings_reject_paddle_sandbox_in_production_without_override() -> None:
    with pytest.raises(ValidationError, match="ALLOW_PADDLE_SANDBOX_IN_PRODUCTION"):
        Settings(environment="production", paddle_environment="sandbox")


def test_settings_allow_paddle_sandbox_in_production_with_explicit_override() -> None:
    settings = Settings(
        environment="production",
        paddle_environment="sandbox",
        allow_paddle_sandbox_in_production=True,
    )

    assert settings.paddle_environment == "sandbox"


def test_settings_include_app_base_url_in_cors_origins() -> None:
    settings = Settings(
        app_base_url="https://app.vitable.cv/auth/login",
        cors_allowed_origins="https://admin.vitable.cv, https://app.vitable.cv",
    )

    assert "https://app.vitable.cv" in settings.effective_cors_allowed_origins
    assert "https://admin.vitable.cv" in settings.effective_cors_allowed_origins
    assert settings.effective_cors_allowed_origins.count("https://app.vitable.cv") == 1
