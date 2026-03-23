from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path

from scrapling.fetchers import FetcherSession

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.job_parsers.adapters.indeed import (  # noqa: E402
    IndeedParser,
    _looks_like_challenge,
)
from src.services.job_parsers.schemas import (  # noqa: E402
    CompanyDetail,
    SearchIntent,
    VacancyDetail,
    VacancySeed,
)

DEFAULT_IMPERSONATION_PROFILES = [
    ["chrome"],
    ["safari"],
    ["firefox"],
]


@dataclass
class ScraplingParserFetchResult:
    html_text: str | None
    duration_seconds: float
    transport: str
    challenge_detected: bool
    error: str | None = None


class IndeedScraplingParser:
    """Experimental Indeed parser that keeps a persistent Scrapling session per run."""

    def __init__(self) -> None:
        self._parser = IndeedParser()

    @property
    def parser(self) -> IndeedParser:
        return self._parser

    def build_search_urls(self, intent: SearchIntent) -> list[str]:
        return self._parser.build_search_urls(intent)

    def open_session(self, impersonate: list[str]) -> FetcherSession:
        return FetcherSession(impersonate=impersonate)

    def fetch_with_session(
        self,
        session: FetcherSession,
        url: str,
        *,
        stage: str,
        timeout_ms: int = 30_000,
    ) -> ScraplingParserFetchResult:
        started = time.perf_counter()
        try:
            response = session.get(
                url,
                stealthy_headers=True,
                timeout=timeout_ms,
            )
            html_text = response.html_content or response.body.decode("utf-8", errors="replace")
            challenge_detected = (
                _looks_like_challenge(html_text, stage=stage) if html_text else True
            )
            return ScraplingParserFetchResult(
                html_text=html_text,
                duration_seconds=time.perf_counter() - started,
                transport="fetcher_session",
                challenge_detected=challenge_detected,
            )
        except Exception as exc:
            return ScraplingParserFetchResult(
                html_text=None,
                duration_seconds=time.perf_counter() - started,
                transport="fetcher_session",
                challenge_detected=True,
                error=str(exc),
            )

    def parse_detail(self, html_text: str, job_url: str, seed: VacancySeed) -> VacancyDetail:
        return self._parser.parse_job_detail_page(html_text, job_url, seed)

    def parse_company(self, html_text: str, company_url: str) -> CompanyDetail | None:
        return self._parser.parse_company_page(html_text, company_url)
