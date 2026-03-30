import importlib

from src.main import create_app


def test_app_registers_onboarding_routes() -> None:
    app = create_app()
    route_paths = {route.path for route in app.routes}

    assert "/onboarding/users/{user_id}/active" in route_paths
    assert "/onboarding/users/{user_id}/run" in route_paths
    assert "/onboarding/users/{user_id}/respond" in route_paths


def test_production_app_hides_openapi_and_docs(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_SECRET_KEY", "prod-secret")

    import src.main as main_module

    reloaded = importlib.reload(main_module)
    try:
        app = reloaded.create_app()
        assert app.docs_url is None
        assert app.redoc_url is None
        assert app.openapi_url is None
    finally:
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("AUTH_SECRET_KEY", raising=False)
        importlib.reload(main_module)
