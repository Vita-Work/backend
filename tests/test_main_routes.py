import src.main as main_module
from src.config import Settings
from src.main import create_app


def test_app_registers_onboarding_routes() -> None:
    app = create_app()
    route_paths = {route.path for route in app.routes}

    assert "/onboarding/users/{user_id}/active" in route_paths
    assert "/onboarding/users/{user_id}/run" in route_paths
    assert "/onboarding/users/{user_id}/respond" in route_paths


def test_app_allows_configured_frontend_origin_for_cors(monkeypatch) -> None:
    monkeypatch.setattr(
        main_module,
        "settings",
        Settings(app_base_url="https://app.vitable.cv"),
    )

    app = create_app()
    cors_middleware = next(
        middleware
        for middleware in app.user_middleware
        if middleware.cls.__name__ == "CORSMiddleware"
    )

    assert "https://app.vitable.cv" in cors_middleware.kwargs["allow_origins"]
