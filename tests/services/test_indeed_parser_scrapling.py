from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest
from src.services.job_parsers.adapters import indeed as indeed_module
from src.services.job_parsers.adapters.indeed import IndeedParser
from src.services.job_parsers.schemas import ScrapeError

LISTING_HTML = """
<html>
  <head><title>Software Engineer Jobs, Employment in New York, NY | Indeed</title></head>
  <body>
    <div id="job_abc123def456ghi7">
      <a class="jcs-JobTitle" data-jk="abc123def456ghi7">Software Engineer</a>
      <span class="companyName">Acme</span>
      <div class="companyLocation">New York, NY</div>
    </div>
  </body>
</html>
"""

DETAIL_HTML = """
<html>
  <head><title>Software Engineer - New York, NY - Indeed.com</title></head>
  <body>
    <h1>Software Engineer</h1>
    <div id="jobDescriptionText">
      Build platform features with Python, APIs, and distributed systems. This description is
      long enough to be considered usable by parser checks.
    </div>
  </body>
</html>
"""

COMPANY_HTML = """
<html>
  <head><title>Acme Careers and Employment | Indeed.com</title></head>
  <body>
    <h1>Acme Careers and Employment</h1>
    <div data-testid="about">Acme builds hiring tools.</div>
  </body>
</html>
"""

SECURITY_CHECK_HTML = """
<html>
  <head><title>Security Check - Indeed.com</title></head>
  <body>Checking your browser before accessing Indeed</body>
</html>
"""

ADDITIONAL_VERIFICATION_HTML = """
<html>
  <head><title>Additional Verification Required</title></head>
  <body>
    <h1>Additional Verification Required</h1>
  </body>
</html>
"""


@dataclass
class FakeResponse:
    status: int
    html_content: str

    @property
    def body(self) -> bytes:
        return self.html_content.encode("utf-8")


class FakeFetcherSession:
    responses_by_profile: dict[tuple[str, ...], list[FakeResponse]] = {}
    created_profiles: list[list[str]] = []
    closed_profiles: list[list[str]] = []

    def __init__(self, impersonate: list[str]) -> None:
        self.profile = impersonate[:]
        self._responses = list(self.responses_by_profile.get(tuple(self.profile), []))

    def __enter__(self) -> FakeFetcherSession:
        self.created_profiles.append(self.profile[:])
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.closed_profiles.append(self.profile[:])

    def get(self, url: str, *, stealthy_headers: bool, timeout: int) -> FakeResponse:
        assert stealthy_headers is True
        assert timeout == 30_000
        if not self._responses:
            raise RuntimeError(f"no_fake_response_for_{self.profile}_{url}")
        return self._responses.pop(0)


@pytest.fixture(autouse=True)
def reset_parser_singleton() -> None:
    IndeedParser._instances.pop(IndeedParser, None)
    FakeFetcherSession.responses_by_profile = {}
    FakeFetcherSession.created_profiles = []
    FakeFetcherSession.closed_profiles = []


def test_fetch_page_text_returns_html_via_scrapling_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(indeed_module, "FetcherSession", FakeFetcherSession)
    FakeFetcherSession.responses_by_profile = {
        ("chrome",): [FakeResponse(200, LISTING_HTML)],
    }
    parser = IndeedParser()
    errors: list[ScrapeError] = []

    html_text = asyncio.run(
        parser.fetch_page_text(
            None,
            "https://www.indeed.com/jobs?q=software+engineer&l=New+York%2C+NY&sort=date",
            stage="listing",
            errors=errors,
        )
    )

    assert "Software Engineer Jobs" in html_text
    assert errors == []
    assert FakeFetcherSession.created_profiles == [["chrome"]]


def test_listing_profile_fallback_uses_safari_after_chrome_security_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(indeed_module, "FetcherSession", FakeFetcherSession)
    FakeFetcherSession.responses_by_profile = {
        ("chrome",): [FakeResponse(403, SECURITY_CHECK_HTML)],
        ("safari",): [FakeResponse(200, LISTING_HTML)],
    }
    parser = IndeedParser()
    errors: list[ScrapeError] = []

    html_text = asyncio.run(
        parser.fetch_page_text(
            None,
            "https://www.indeed.com/jobs?q=software+engineer&l=New+York%2C+NY&sort=date",
            stage="listing",
            errors=errors,
        )
    )

    assert "Software Engineer Jobs" in html_text
    assert errors == []
    assert FakeFetcherSession.created_profiles == [["chrome"], ["safari"]]
    assert parser._active_profile == ["safari"]


def test_challenge_detected_returns_none_and_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(indeed_module, "FetcherSession", FakeFetcherSession)
    FakeFetcherSession.responses_by_profile = {
        ("chrome",): [FakeResponse(403, SECURITY_CHECK_HTML)],
        ("safari",): [FakeResponse(403, SECURITY_CHECK_HTML)],
    }
    parser = IndeedParser()
    errors: list[ScrapeError] = []

    html_text = asyncio.run(
        parser.fetch_page_text(
            None,
            "https://www.indeed.com/jobs?q=frontend+developer&l=Remote&sort=date",
            stage="listing",
            errors=errors,
        )
    )

    assert html_text is None
    assert len(errors) == 1
    assert "http_status_403" in errors[0].message or "challenge_detected" in errors[0].message


def test_successful_listing_reuses_same_profile_for_detail_and_company(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(indeed_module, "FetcherSession", FakeFetcherSession)
    FakeFetcherSession.responses_by_profile = {
        ("chrome",): [
            FakeResponse(200, LISTING_HTML),
            FakeResponse(200, DETAIL_HTML),
            FakeResponse(200, COMPANY_HTML),
        ],
    }
    parser = IndeedParser()

    listing_errors: list[ScrapeError] = []
    detail_errors: list[ScrapeError] = []
    company_errors: list[ScrapeError] = []

    listing_html = asyncio.run(
        parser.fetch_page_text(
            None,
            "https://www.indeed.com/jobs?q=software+engineer&l=New+York%2C+NY&sort=date",
            stage="listing",
            errors=listing_errors,
        )
    )
    seed = parser.parse_listing_page(listing_html, "").vacancies[0]
    detail_html = asyncio.run(
        parser.fetch_page_text(
            None,
            seed.job_url,
            stage="detail",
            errors=detail_errors,
        )
    )
    company_html = asyncio.run(
        parser.fetch_page_text(
            None,
            "https://www.indeed.com/cmp/Acme",
            stage="company",
            errors=company_errors,
        )
    )

    assert "Software Engineer" in detail_html
    assert "Acme Careers" in company_html
    assert listing_errors == []
    assert detail_errors == []
    assert company_errors == []
    assert FakeFetcherSession.created_profiles == [["chrome"]]


def test_detail_verification_page_returns_none_and_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(indeed_module, "FetcherSession", FakeFetcherSession)
    FakeFetcherSession.responses_by_profile = {
        ("chrome",): [
            FakeResponse(200, LISTING_HTML),
            FakeResponse(200, ADDITIONAL_VERIFICATION_HTML),
        ],
    }
    parser = IndeedParser()
    listing_errors: list[ScrapeError] = []
    detail_errors: list[ScrapeError] = []

    listing_html = asyncio.run(
        parser.fetch_page_text(
            None,
            "https://www.indeed.com/jobs?q=software+engineer&l=New+York%2C+NY&sort=date",
            stage="listing",
            errors=listing_errors,
        )
    )
    seed = parser.parse_listing_page(listing_html, "").vacancies[0]
    detail_html = asyncio.run(
        parser.fetch_page_text(
            None,
            seed.job_url,
            stage="detail",
            errors=detail_errors,
        )
    )

    assert detail_html is None
    assert len(detail_errors) == 1
    assert detail_errors[0].message == "detail_unusable_page"
