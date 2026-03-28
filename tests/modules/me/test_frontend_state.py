from src.modules.me.frontend_state import route_for_app_phase


def test_route_for_app_phase_matches_frontend_routes() -> None:
    assert route_for_app_phase("new_user") == "/onboarding"
    assert route_for_app_phase("upload_cv") == "/onboarding"
    assert route_for_app_phase("processing_cv") == "/onboarding/processing"
    assert route_for_app_phase("onboarding_chat") == "/onboarding/chat"
    assert route_for_app_phase("awaiting_confirmation") == "/onboarding/chat"
    assert route_for_app_phase("searching_jobs") == "/searching"
    assert route_for_app_phase("results_ready") == "/results"
