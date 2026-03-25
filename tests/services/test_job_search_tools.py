import asyncio

import pytest
from src.services.job_parsers.schemas import ListingPageResult, VacancySeed
from src.services.job_search_tools import ListSiteJobsArgs, get_job_site_tools_service
from src.services.job_search_tools import service as service_module


def test_get_site_profile_returns_parser_capabilities() -> None:
    toolset = get_job_site_tools_service("hh")

    profile = toolset.get_site_profile()

    assert profile.site == "hh"
    assert profile.label == "HeadHunter Russia"
    assert profile.supports_native_query_search is True
    assert "RU" in profile.allowed_countries


def test_list_site_jobs_monitoring_mode_skips_seen_jobs_and_stops_stale_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeParser:
        def supports_native_query_search(self) -> bool:
            return True

        def build_search_urls(self, intent) -> list[str]:
            assert intent.search_text == "python backend"
            return ["https://fake.example/search?page=1"]

        async def fetch_page_text(self, client, url: str, *, stage: str, errors):
            _ = client, stage, errors
            return url

        def parse_listing_page(self, html_text: str, page_url: str) -> ListingPageResult:
            if "page=1" in html_text:
                return ListingPageResult(
                    vacancies=[
                        VacancySeed(
                            job_url="https://fake.example/jobs/old-role",
                            title="Backend Engineer",
                            company_name="Acme",
                            location="Remote",
                        ),
                        VacancySeed(
                            job_url="https://fake.example/jobs/new-role",
                            title="Platform Engineer",
                            company_name="Nova",
                            location="Remote",
                        ),
                    ],
                    next_page_url="https://fake.example/search?page=2",
                )
            return ListingPageResult(
                vacancies=[
                    VacancySeed(
                        job_url="https://fake.example/jobs/old-role-2",
                        title="Backend Engineer",
                        company_name="Acme",
                        location="Remote",
                    )
                ],
                next_page_url="https://fake.example/search?page=3",
            )

    monkeypatch.setattr(service_module, "get_parser", lambda site_name: FakeParser())

    toolset = get_job_site_tools_service("fake")
    listings = asyncio.run(
        toolset.list_site_jobs(
            args=ListSiteJobsArgs(
                search_text="python backend",
                monitoring_mode=True,
                seen_job_urls=["https://fake.example/jobs/old-role"],
                seen_job_fingerprints=["backend engineer|acme|remote"],
                max_pages=3,
                max_items=10,
                max_stale_pages=1,
            )
        )
    )

    assert [listing.job_url for listing in listings] == ["https://fake.example/jobs/new-role"]
