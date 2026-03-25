from src.main import create_app


def test_app_registers_onboarding_routes() -> None:
    app = create_app()
    route_paths = {route.path for route in app.routes}

    assert "/onboarding/users/{user_id}/active" in route_paths
    assert "/onboarding/users/{user_id}/run" in route_paths
    assert "/onboarding/users/{user_id}/respond" in route_paths
