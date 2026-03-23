from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx
from scrapling.fetchers import Fetcher, StealthyFetcher

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.job_parsers.adapters.indeed import (  # noqa: E402
    IndeedParser,
    _looks_like_challenge,
)
from src.services.job_parsers.schemas import (  # noqa: E402
    ScrapeError,
    SearchIntent,
    VacancyRecord,
    VacancySeed,
)


@dataclass(frozen=True)
class QueryCase:
    label: str
    search_text: str
    locations: list[str]
    remote_only: bool = False

    def to_intent(self) -> SearchIntent:
        return SearchIntent(
            role=self.search_text,
            search_text=self.search_text,
            locations=self.locations,
            remote_only=self.remote_only,
        )


@dataclass
class QueryRunMetrics:
    query_label: str
    runner: str
    search_urls: list[str]
    listing_pages_requested: int
    listing_pages_parsed: int
    listing_fetches_with_challenge: int
    listing_seeds_found: int
    unique_jobs_found: int
    details_attempted: int
    details_succeeded: int
    details_usable: int
    detail_fetches_with_challenge: int
    company_attempted: int
    company_succeeded: int
    company_fetches_with_challenge: int
    records_built: int
    records_usable: int
    errors_count: int
    total_seconds: float
    listing_seconds: float
    detail_seconds: float
    company_seconds: float
    job_urls: list[str]
    sample_titles: list[str]
    error_samples: list[str]


DEFAULT_QUERIES = [
    QueryCase(
        label="software engineer / New York, NY",
        search_text="software engineer",
        locations=["New York, NY"],
    ),
    QueryCase(
        label="frontend developer / Remote",
        search_text="frontend developer",
        locations=["Remote"],
        remote_only=True,
    ),
    QueryCase(
        label="devops engineer / Austin, TX",
        search_text="devops engineer",
        locations=["Austin, TX"],
    ),
]


class CurrentIndeedRunner:
    name = "current_parser"

    def __init__(self, parser: IndeedParser) -> None:
        self.parser = parser

    async def fetch_page_text(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        stage: str,
        errors: list[ScrapeError],
    ) -> str | None:
        return await self.parser.fetch_page_text(client, url, stage=stage, errors=errors)


class ScraplingIndeedRunner:
    def __init__(self, *, mode: str = "fetcher") -> None:
        self.mode = mode
        self.name = f"scrapling_{mode}"

    async def fetch_page_text(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        stage: str,
        errors: list[ScrapeError],
    ) -> str | None:
        del client
        started = time.perf_counter()
        try:
            return await asyncio.to_thread(self._fetch_sync, url)
        except Exception as exc:
            errors.append(
                ScrapeError(
                    stage=stage,
                    url=url,
                    message=f"scrapling_{self.mode}_fetch_failed: {exc}",
                )
            )
            return None
        finally:
            _ = time.perf_counter() - started

    def _fetch_sync(self, url: str) -> str:
        if self.mode == "stealthy":
            response = StealthyFetcher.fetch(
                url,
                headless=True,
                network_idle=True,
                timeout=30_000,
                wait=1_500,
                solve_cloudflare=True,
                disable_resources=False,
            )
        else:
            response = Fetcher.get(
                url,
                timeout=30_000,
                stealthy_headers=True,
            )

        html_text = response.html_content or response.body.decode("utf-8", errors="replace")
        if not html_text:
            raise RuntimeError("empty_html")
        return html_text


async def _run_query(
    *,
    parser: IndeedParser,
    runner: CurrentIndeedRunner | ScraplingIndeedRunner,
    query: QueryCase,
    max_pages: int,
    max_details: int,
) -> QueryRunMetrics:
    intent = query.to_intent()
    errors: list[ScrapeError] = []
    search_urls = parser.build_search_urls(intent)
    queue = list(search_urls)
    visited_pages: set[str] = set()
    listing_seeds: dict[str, VacancySeed] = {}
    records: list[VacancyRecord] = []

    listing_seconds = 0.0
    detail_seconds = 0.0
    company_seconds = 0.0
    listing_challenges = 0
    detail_challenges = 0
    company_challenges = 0
    listing_pages_parsed = 0
    details_succeeded = 0
    details_usable = 0
    company_attempted = 0
    company_succeeded = 0

    total_started = time.perf_counter()

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        while queue and len(visited_pages) < max_pages:
            page_url = queue.pop(0)
            if page_url in visited_pages:
                continue

            visited_pages.add(page_url)
            page_started = time.perf_counter()
            html_text = await runner.fetch_page_text(
                client,
                page_url,
                stage="listing",
                errors=errors,
            )
            listing_seconds += time.perf_counter() - page_started
            if html_text is None:
                continue
            if _looks_like_challenge(html_text, stage="listing"):
                listing_challenges += 1

            listing = parser.parse_listing_page(html_text, page_url)
            listing_pages_parsed += 1
            for seed in listing.vacancies:
                canonical_url = parser._canonical_job_url(seed.job_url)
                if canonical_url not in listing_seeds:
                    listing_seeds[canonical_url] = seed.model_copy(
                        update={"job_url": canonical_url}
                    )

            if (
                listing.next_page_url
                and listing.next_page_url not in visited_pages
                and len(visited_pages) < max_pages
            ):
                queue.append(listing.next_page_url)

        selected_seeds = list(listing_seeds.values())[:max_details]

        for seed in selected_seeds:
            detail_started = time.perf_counter()
            detail_html = await runner.fetch_page_text(
                client,
                seed.job_url,
                stage="detail",
                errors=errors,
            )
            detail_seconds += time.perf_counter() - detail_started
            if detail_html is None:
                continue
            detail_is_challenge = _looks_like_challenge(detail_html, stage="detail")
            if detail_is_challenge:
                detail_challenges += 1

            try:
                detail = parser.parse_job_detail_page(detail_html, seed.job_url, seed)
            except Exception as exc:
                errors.append(ScrapeError(stage="detail_parse", url=seed.job_url, message=str(exc)))
                continue

            details_succeeded += 1
            if not detail_is_challenge and _is_usable_detail(detail):
                details_usable += 1

            company = None
            company_url = detail.company_url or seed.company_url
            if company_url:
                company_attempted += 1
                company_started = time.perf_counter()
                company_html = await runner.fetch_page_text(
                    client,
                    company_url,
                    stage="company",
                    errors=errors,
                )
                company_seconds += time.perf_counter() - company_started
                if company_html is not None:
                    if _looks_like_challenge(company_html, stage="company"):
                        company_challenges += 1
                    try:
                        company = parser.parse_company_page(company_html, company_url)
                    except Exception as exc:
                        errors.append(
                            ScrapeError(stage="company_parse", url=company_url, message=str(exc))
                        )
                    else:
                        if company is not None:
                            company_succeeded += 1

            record = parser._build_record(seed=seed, detail=detail, company=company)
            records.append(record)

    total_seconds = time.perf_counter() - total_started
    return QueryRunMetrics(
        query_label=query.label,
        runner=runner.name,
        search_urls=search_urls,
        listing_pages_requested=len(visited_pages),
        listing_pages_parsed=listing_pages_parsed,
        listing_fetches_with_challenge=listing_challenges,
        listing_seeds_found=len(listing_seeds),
        unique_jobs_found=len(listing_seeds),
        details_attempted=min(max_details, len(listing_seeds)),
        details_succeeded=details_succeeded,
        details_usable=details_usable,
        detail_fetches_with_challenge=detail_challenges,
        company_attempted=company_attempted,
        company_succeeded=company_succeeded,
        company_fetches_with_challenge=company_challenges,
        records_built=len(records),
        records_usable=sum(1 for record in records if _is_usable_record(record)),
        errors_count=len(errors),
        total_seconds=round(total_seconds, 3),
        listing_seconds=round(listing_seconds, 3),
        detail_seconds=round(detail_seconds, 3),
        company_seconds=round(company_seconds, 3),
        job_urls=[record.job_url for record in records],
        sample_titles=[record.title or "" for record in records[:5]],
        error_samples=[error.message for error in errors[:5]],
    )


def _build_markdown_report(results: list[QueryRunMetrics]) -> str:
    grouped: dict[str, list[QueryRunMetrics]] = {}
    for result in results:
        grouped.setdefault(result.query_label, []).append(result)

    lines = [
        "# Indeed parsing comparison",
        "",
        (
            "| Query | Runner | Listing seeds | Detail ok | Company ok | Records | Errors | "
            "Time, s | Listing s | Detail s | Company s | URL overlap vs current |"
        ),
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for query_label, query_results in grouped.items():
        baseline = next((item for item in query_results if item.runner == "current_parser"), None)
        baseline_urls = set(baseline.job_urls) if baseline is not None else set()
        for item in sorted(query_results, key=lambda value: value.runner):
            overlap = (
                len(set(item.job_urls) & baseline_urls)
                if baseline_urls
                else len(set(item.job_urls))
            )
            lines.append(
                "| "
                f"{query_label} | "
                f"{item.runner} | "
                f"{item.listing_seeds_found} | "
                f"{item.details_usable}/{item.details_attempted} usable "
                f"({item.details_succeeded} parsed) | "
                f"{item.company_succeeded}/{item.company_attempted} | "
                f"{item.records_usable}/{item.records_built} usable | "
                f"{item.errors_count} | "
                f"{item.total_seconds:.3f} | "
                f"{item.listing_seconds:.3f} | "
                f"{item.detail_seconds:.3f} | "
                f"{item.company_seconds:.3f} | "
                f"{overlap} |"
            )

    lines.append("")
    lines.append("## Notes")
    for item in results:
        sample_titles = ", ".join(title for title in item.sample_titles if title) or "n/a"
        error_samples = "; ".join(item.error_samples) or "n/a"
        lines.append(
            f"- **{item.query_label} / {item.runner}**: "
            f"listing_challenges={item.listing_fetches_with_challenge}, "
            f"detail_challenges={item.detail_fetches_with_challenge}, "
            f"company_challenges={item.company_fetches_with_challenge}, "
            f"sample_titles={sample_titles}, "
            f"error_samples={error_samples}"
        )

    return "\n".join(lines)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare the current Indeed parser with a Scrapling-based fetch implementation."
    )
    parser.add_argument(
        "--scrapling-mode",
        choices=("fetcher", "stealthy"),
        default="fetcher",
        help="Scrapling transport mode. 'fetcher' is the fastest and most stable default.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help="How many listing pages per query to crawl.",
    )
    parser.add_argument(
        "--max-details",
        type=int,
        default=5,
        help="How many job details per query to enrich.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        help="Optional path for raw JSON metrics.",
    )
    parser.add_argument(
        "--markdown-out",
        type=Path,
        help="Optional path for the markdown report.",
    )
    return parser


def _is_usable_detail(detail: Any) -> bool:
    title = (getattr(detail, "title", "") or "").strip().lower()
    description = (getattr(detail, "description", "") or "").strip()
    if not title:
        return False
    if "additional verification required" in title:
        return False
    if "we can’t find this page" in title or "we can't find this page" in title:
        return False
    return len(description) >= 80


def _is_usable_record(record: VacancyRecord) -> bool:
    title = (record.title or "").strip().lower()
    description = (record.description or "").strip()
    if not title:
        return False
    if "additional verification required" in title:
        return False
    if "we can’t find this page" in title or "we can't find this page" in title:
        return False
    return len(description) >= 80


async def _main() -> None:
    args = _build_arg_parser().parse_args()
    parser = IndeedParser()
    runners = [
        CurrentIndeedRunner(parser),
        ScraplingIndeedRunner(mode=args.scrapling_mode),
    ]

    results: list[QueryRunMetrics] = []
    for query in DEFAULT_QUERIES:
        for runner in runners:
            results.append(
                await _run_query(
                    parser=parser,
                    runner=runner,
                    query=query,
                    max_pages=args.max_pages,
                    max_details=args.max_details,
                )
            )

    if hasattr(parser, "_reset_playwright_runtime"):
        await parser._reset_playwright_runtime()

    markdown_report = _build_markdown_report(results)
    print(markdown_report)

    if args.json_out:
        args.json_out.write_text(
            json.dumps([asdict(item) for item in results], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if args.markdown_out:
        args.markdown_out.write_text(markdown_report, encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(_main())
