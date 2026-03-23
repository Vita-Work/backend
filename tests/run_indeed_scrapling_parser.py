from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.job_parsers.adapters.indeed import _looks_like_challenge  # noqa: E402
from src.services.job_parsers.schemas import SearchIntent  # noqa: E402
from tests.indeed_scrapling_parser import (  # noqa: E402
    DEFAULT_IMPERSONATION_PROFILES,
    IndeedScraplingParser,
)


@dataclass
class QueryResult:
    query: str
    location: str
    listing_seeds: int
    details_attempted: int
    details_usable: int
    companies_attempted: int
    companies_usable: int
    impersonation_profile: list[str]
    listing_transport: str
    detail_transports: list[str]
    company_transports: list[str]
    listing_seconds: float
    detail_seconds: float
    company_seconds: float
    total_seconds: float
    sample_titles: list[str]
    sample_errors: list[str]


DEFAULT_CASES = [
    ("software engineer", "New York, NY"),
    ("frontend developer", "Remote"),
    ("devops engineer", "Austin, TX"),
]


def _is_usable_title(title: str | None) -> bool:
    normalized = (title or "").strip().lower()
    if not normalized:
        return False
    if "additional verification required" in normalized:
        return False
    if "we can’t find this page" in normalized or "we can't find this page" in normalized:
        return False
    return True


def _is_usable_detail(title: str | None, description: str | None) -> bool:
    return _is_usable_title(title) and len((description or "").strip()) >= 80


def run_case(search_text: str, location: str, max_details: int) -> QueryResult:
    parser = IndeedScraplingParser()
    intent = SearchIntent(
        role=search_text,
        search_text=search_text,
        locations=[location],
        remote_only=location.lower() == "remote",
    )

    sample_titles: list[str] = []
    sample_errors: list[str] = []
    detail_transports: list[str] = []
    company_transports: list[str] = []

    total_started = __import__("time").perf_counter()

    search_url = parser.build_search_urls(intent)[0]
    selected_profile: list[str] = []
    listing_result = None
    listing = None
    listing_seconds = 0.0
    detail_seconds = 0.0
    company_seconds = 0.0
    details_usable = 0
    companies_attempted = 0
    companies_usable = 0
    seeds = []

    for profile in DEFAULT_IMPERSONATION_PROFILES:
        with parser.open_session(profile) as session:
            attempt_listing_result = parser.fetch_with_session(session, search_url, stage="listing")
            listing_seconds += attempt_listing_result.duration_seconds
            if attempt_listing_result.html_text is None:
                if attempt_listing_result.error:
                    sample_errors.append(attempt_listing_result.error)
                continue

            if attempt_listing_result.challenge_detected:
                continue

            attempt_listing = parser.parser.parse_listing_page(
                attempt_listing_result.html_text, search_url
            )
            if not attempt_listing.vacancies:
                continue

            selected_profile = profile
            listing_result = attempt_listing_result
            listing = attempt_listing
            seeds = listing.vacancies[:max_details]

            for seed in seeds:
                detail_result = parser.fetch_with_session(session, seed.job_url, stage="detail")
                detail_seconds += detail_result.duration_seconds
                detail_transports.append(detail_result.transport)
                if detail_result.html_text is None:
                    if detail_result.error:
                        sample_errors.append(detail_result.error)
                    continue

                detail_is_challenge = _looks_like_challenge(
                    detail_result.html_text,
                    stage="detail",
                )
                detail = parser.parse_detail(detail_result.html_text, seed.job_url, seed)
                if _is_usable_detail(detail.title, detail.description) and not detail_is_challenge:
                    details_usable += 1
                if len(sample_titles) < 5 and detail.title:
                    sample_titles.append(detail.title)

                company_url = detail.company_url or seed.company_url
                if not company_url:
                    continue

                companies_attempted += 1
                company_result = parser.fetch_with_session(session, company_url, stage="company")
                company_seconds += company_result.duration_seconds
                company_transports.append(company_result.transport)
                if company_result.html_text is None:
                    if company_result.error:
                        sample_errors.append(company_result.error)
                    continue

                company_is_challenge = _looks_like_challenge(
                    company_result.html_text, stage="company"
                )
                company = parser.parse_company(company_result.html_text, company_url)
                if company is not None and company.company_name and not company_is_challenge:
                    companies_usable += 1
            break

    if listing_result is None or listing is None:
        return QueryResult(
            query=search_text,
            location=location,
            listing_seeds=0,
            details_attempted=0,
            details_usable=0,
            companies_attempted=0,
            companies_usable=0,
            impersonation_profile=selected_profile,
            listing_transport="fetcher_session",
            detail_transports=[],
            company_transports=[],
            listing_seconds=round(listing_seconds, 3),
            detail_seconds=0.0,
            company_seconds=0.0,
            total_seconds=round(__import__("time").perf_counter() - total_started, 3),
            sample_titles=[],
            sample_errors=sample_errors[:5],
        )

    total_seconds = __import__("time").perf_counter() - total_started
    return QueryResult(
        query=search_text,
        location=location,
        listing_seeds=len(listing.vacancies),
        details_attempted=len(seeds),
        details_usable=details_usable,
        companies_attempted=companies_attempted,
        companies_usable=companies_usable,
        impersonation_profile=selected_profile,
        listing_transport=listing_result.transport,
        detail_transports=detail_transports,
        company_transports=company_transports,
        listing_seconds=round(listing_seconds, 3),
        detail_seconds=round(detail_seconds, 3),
        company_seconds=round(company_seconds, 3),
        total_seconds=round(total_seconds, 3),
        sample_titles=sample_titles,
        sample_errors=sample_errors[:5],
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the new experimental Indeed Scrapling parser."
    )
    parser.add_argument("--max-details", type=int, default=5)
    parser.add_argument("--json-out", type=Path)
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    results = [run_case(query, location, args.max_details) for query, location in DEFAULT_CASES]

    print("# Indeed Scrapling session parser report")
    print("")
    print(
        "| Query | Listing seeds | Usable details | Usable companies | "
        "Listing transport | Total s |"
    )
    print("| --- | ---: | ---: | ---: | --- | ---: |")
    for item in results:
        print(
            f"| {item.query} / {item.location} | "
            f"{item.listing_seeds} | "
            f"{item.details_usable}/{item.details_attempted} | "
            f"{item.companies_usable}/{item.companies_attempted} | "
            f"{item.listing_transport} ({item.impersonation_profile}) | "
            f"{item.total_seconds:.3f} |"
        )

    print("")
    print("## Notes")
    for item in results:
        print(
            f"- **{item.query} / {item.location}**: "
            f"profile={item.impersonation_profile}, "
            f"detail_transports={item.detail_transports}, "
            f"company_transports={item.company_transports}, "
            f"sample_titles={', '.join(item.sample_titles) or 'n/a'}, "
            f"sample_errors={'; '.join(item.sample_errors) or 'n/a'}"
        )

    if args.json_out:
        args.json_out.write_text(
            json.dumps([asdict(item) for item in results], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
