from src.services.job_search_tools import get_job_site_tools_service


def test_get_site_profile_returns_parser_capabilities() -> None:
    toolset = get_job_site_tools_service("hh")

    profile = toolset.get_site_profile()

    assert profile.site == "hh"
    assert profile.label == "HeadHunter Russia"
    assert profile.supports_native_query_search is True
    assert "RU" in profile.allowed_countries
