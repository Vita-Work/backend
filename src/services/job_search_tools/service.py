from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from pydantic import BaseModel, Field

from src.logger import get_logger
from src.services import job_parsers as _job_parsers  # noqa: F401
from src.services.job_parsers.registry import get_parser
from src.services.job_parsers.schemas import (
    CompanyDetail,
    ScrapeError,
    SearchIntent,
    VacancyDetail,
    VacancyRecord,
    VacancySeed,
)
from src.workflows.search_job.schemas import SiteJobDetail, SiteJobListing

logger = get_logger("services.job_search_tools")

SITE_METADATA: dict[str, dict[str, object]] = {
    "indeed": {
        "label": "Indeed",
        "allowed_countries": ["US"],
        "notes": "General US-focused search surface in this project.",
    },
    "hh": {
        "label": "HeadHunter Russia",
        "allowed_countries": ["RU"],
        "notes": "Official hh.ru API adapter.",
    },
    "habr_career": {
        "label": "Habr Career",
        "allowed_countries": ["RU"],
        "notes": "Russian-language tech jobs market.",
    },
    "devkg": {
        "label": "DevKG",
        "allowed_countries": ["KG"],
        "notes": "Current parser reports no native query-search support.",
    },
    "computrabajo": {
        "label": "Computrabajo Mexico",
        "allowed_countries": ["MX"],
        "notes": "Current implementation is bound to mx.computrabajo.com.",
    },
    "getonbrd": {
        "label": "Get on Board LATAM",
        "allowed_countries": [
            "AR",
            "BO",
            "BR",
            "CL",
            "CO",
            "CR",
            "DO",
            "EC",
            "SV",
            "GT",
            "HN",
            "MX",
            "NI",
            "PA",
            "PE",
            "PY",
            "UY",
            "VE",
        ],
        "notes": "LATAM-focused market with public API-backed search.",
    },
}


class SiteProfileResult(BaseModel):
    site: str
    label: str
    supports_native_query_search: bool
    allowed_countries: list[str] = Field(default_factory=list)
    notes: str | None = None


class ListSiteJobsArgs(BaseModel):
    search_text: str
    locations: list[str] = Field(default_factory=list)
    remote_only: bool = False
    salary_from: int | None = None
    max_pages: int = Field(default=1, ge=1, le=3)
    max_items: int = Field(default=10, ge=1, le=20)


@dataclass
class JobSiteToolsService:
    """Three-tool contract for a single site agent."""

    site_name: str
    timeout_seconds: float = 20.0
    _seed_cache: dict[str, VacancySeed] = field(default_factory=dict)

    def get_site_profile(self) -> SiteProfileResult:
        parser = get_parser(self.site_name)
        metadata = SITE_METADATA.get(self.site_name, {})
        return SiteProfileResult(
            site=self.site_name,
            label=str(metadata.get("label", self.site_name)),
            supports_native_query_search=parser.supports_native_query_search(),
            allowed_countries=list(metadata.get("allowed_countries", [])),
            notes=str(metadata.get("notes")) if metadata.get("notes") is not None else None,
        )

    async def list_site_jobs(self, *, args: ListSiteJobsArgs) -> list[SiteJobListing]:
        parser = get_parser(self.site_name)
        if not parser.supports_native_query_search():
            return []

        intent = SearchIntent(
            role=args.search_text,
            search_text=args.search_text,
            locations=args.locations,
            remote_only=args.remote_only,
            salary_from=args.salary_from,
        )

        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            follow_redirects=True,
        ) as client:
            search_urls = parser.build_search_urls(intent)
            results: list[SiteJobListing] = []
            visited: set[str] = set()
            queue = list(search_urls)

            while queue and len(visited) < args.max_pages and len(results) < args.max_items:
                page_url = queue.pop(0)
                if page_url in visited:
                    continue
                visited.add(page_url)

                errors: list[ScrapeError] = []
                html_text = await parser.fetch_page_text(
                    client,
                    page_url,
                    stage="listing",
                    errors=errors,
                )
                if html_text is None:
                    continue

                listing = parser.parse_listing_page(html_text, page_url)
                for seed in listing.vacancies:
                    canonical_url = self._canonical_job_url(seed.job_url)
                    self._seed_cache[canonical_url] = seed.model_copy(
                        update={"job_url": canonical_url}
                    )
                    results.append(
                        SiteJobListing(
                            site=self.site_name,
                            title=seed.title,
                            company_name=seed.company_name,
                            location=seed.location,
                            salary_text=seed.salary_text,
                            published_at=seed.published_at,
                            job_url=canonical_url,
                            company_url=seed.company_url,
                        )
                    )
                    if len(results) >= args.max_items:
                        break

                if listing.next_page_url and listing.next_page_url not in visited:
                    queue.append(listing.next_page_url)

        logger.info(
            "job_site_listings_collected",
            site=self.site_name,
            listings_count=len(results),
        )
        return results

    async def get_job_details(self, *, job_urls: list[str]) -> list[SiteJobDetail]:
        parser = get_parser(self.site_name)
        details: list[SiteJobDetail] = []
        requested_job_urls = job_urls[:15]

        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            follow_redirects=True,
        ) as client:
            for raw_job_url in requested_job_urls:
                job_url = self._canonical_job_url(raw_job_url)
                seed = self._seed_cache.get(job_url)
                if seed is None:
                    logger.info(
                        "job_site_detail_missing_seed",
                        site=self.site_name,
                        job_url=job_url,
                    )
                    continue

                errors: list[ScrapeError] = []
                detail_html = await parser.fetch_page_text(
                    client,
                    job_url,
                    stage="detail",
                    errors=errors,
                )
                if detail_html is None:
                    fallback_record = parser.build_fallback_record(seed)
                    if fallback_record is not None:
                        details.append(self._detail_from_record(fallback_record))
                    continue

                try:
                    detail = parser.parse_job_detail_page(detail_html, job_url, seed)
                except Exception as exc:
                    logger.error(
                        "job_site_detail_parse_failed",
                        site=self.site_name,
                        job_url=job_url,
                        error=str(exc),
                        exc_info=True,
                    )
                    fallback_record = parser.build_fallback_record(seed)
                    if fallback_record is not None:
                        details.append(self._detail_from_record(fallback_record))
                    continue

                company = await self._load_company_detail(
                    client=client,
                    parser=parser,
                    detail=detail,
                    seed=seed,
                )
                record = parser._build_record(seed=seed, detail=detail, company=company)
                details.append(self._detail_from_record(record))

        logger.info(
            "job_site_details_collected",
            site=self.site_name,
            details_count=len(details),
        )
        return details

    async def _load_company_detail(
        self,
        *,
        client: httpx.AsyncClient,
        parser,
        detail: VacancyDetail,
        seed: VacancySeed,
    ) -> CompanyDetail | None:
        company_url = detail.company_url or seed.company_url
        if not company_url:
            return None

        errors: list[ScrapeError] = []
        company_html = await parser.fetch_page_text(
            client,
            company_url,
            stage="company",
            errors=errors,
        )
        if company_html is None:
            return None
        try:
            return parser.parse_company_page(company_html, company_url)
        except Exception as exc:
            logger.error(
                "job_site_company_parse_failed",
                site=self.site_name,
                company_url=company_url,
                error=str(exc),
                exc_info=True,
            )
            return None

    @staticmethod
    def _detail_from_record(record: VacancyRecord) -> SiteJobDetail:
        return SiteJobDetail(
            site=record.site,
            job_url=record.job_url,
            title=record.title,
            company_name=record.company_name,
            location=record.location,
            salary_text=record.salary_text,
            salary_min=record.salary_min,
            salary_max=record.salary_max,
            currency=record.currency,
            employment_type=record.employment_type,
            published_at=record.published_at,
            description=record.description,
            skills=record.skills,
            apply_url=record.apply_url,
            company_url=record.company_url,
            company_about=record.company_about,
            company_contacts=record.company_contacts,
            raw_meta=record.raw_meta,
        )

    @staticmethod
    def _canonical_job_url(job_url: str) -> str:
        parsed = httpx.URL(job_url)
        return str(parsed.copy_with(fragment=None))


def get_job_site_tools_service(site_name: str) -> JobSiteToolsService:
    return JobSiteToolsService(site_name=site_name)
