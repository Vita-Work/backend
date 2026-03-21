from __future__ import annotations

import asyncio
import time
from abc import ABCMeta, abstractmethod
from typing import Any
from urllib.parse import urldefrag, urlsplit, urlunsplit

import httpx

from src.config import get_settings
from src.logger import get_logger
from src.services.job_parsers.query_expansion import build_query_terms
from src.services.job_parsers.schemas import (
    CompanyDetail,
    ListingPageResult,
    ScrapeError,
    ScrapeRunResult,
    SearchIntent,
    SiteQueryPlan,
    VacancyDetail,
    VacancyRecord,
    VacancySeed,
)

logger = get_logger("services.job_parsers")


class SingletonMeta(type):
    _instances: dict[type, BaseJobParser] = {}

    def __call__(cls, *args: Any, **kwargs: Any):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class SingletonABCMeta(SingletonMeta, ABCMeta):
    pass


class BaseJobParser(metaclass=SingletonABCMeta):
    @abstractmethod
    def site_code(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def supports_native_query_search(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def build_search_urls(self, intent: SearchIntent) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def parse_listing_page(self, html: str, page_url: str) -> ListingPageResult:
        raise NotImplementedError

    @abstractmethod
    def parse_job_detail_page(self, html: str, job_url: str, seed: VacancySeed) -> VacancyDetail:
        raise NotImplementedError

    @abstractmethod
    def parse_company_page(self, html: str, company_url: str) -> CompanyDetail | None:
        raise NotImplementedError

    def build_fallback_record(self, seed: VacancySeed) -> VacancyRecord | None:
        return None

    def build_request_headers(self, stage: str) -> dict[str, str]:
        return {}

    async def fetch_page_text(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        stage: str,
        errors: list[ScrapeError],
    ) -> str | None:
        headers = self.build_request_headers(stage)
        try:
            response = await client.get(url, headers=headers or None)
            response.raise_for_status()
            return response.text
        except Exception as exc:
            errors.append(ScrapeError(stage=stage, url=url, message=str(exc)))
            logger.error(
                "http_request_failed",
                site=self.site_code(),
                stage=stage,
                url=url,
                error=str(exc),
            )
            return None

    def build_query_terms(self, intent: SearchIntent) -> list[str]:
        return build_query_terms(intent)

    async def scrape_by_intent(
        self,
        intent: SearchIntent,
        *,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 20.0,
        max_pages_safety: int = 100,
    ) -> ScrapeRunResult:
        site = self.site_code()
        query_terms = self.build_query_terms(intent)

        if not self.supports_native_query_search():
            query_plan = SiteQueryPlan(site=site, terms=query_terms, search_urls=[])
            logger.info("site_skipped", site=site, reason="native_query_search_not_supported")
            return ScrapeRunResult(
                site=site,
                status="skipped",
                skip_reason="native_query_search_not_supported",
                query_plan=query_plan,
            )

        search_urls = self.build_search_urls(intent)
        query_plan = SiteQueryPlan(site=site, terms=query_terms, search_urls=search_urls)
        logger.info(
            "query_plan_built",
            site=site,
            terms_count=len(query_terms),
            search_urls_count=len(search_urls),
        )

        if not search_urls:
            return ScrapeRunResult(
                site=site,
                status="failed",
                query_plan=query_plan,
                errors=[ScrapeError(stage="query_plan", message="no_search_urls_built")],
            )

        return await self._scrape_from_query_plan(
            intent,
            query_plan=query_plan,
            client=client,
            timeout_seconds=timeout_seconds,
            max_pages_safety=max_pages_safety,
        )

    async def _scrape_from_query_plan(
        self,
        intent: SearchIntent,
        *,
        query_plan: SiteQueryPlan,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 20.0,
        max_pages_safety: int = 100,
    ) -> ScrapeRunResult:
        site = self.site_code()
        search_urls = query_plan.search_urls
        start_ts = time.perf_counter()
        own_client = client is None
        http_client = client or httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True)

        errors: list[ScrapeError] = []
        listing_seeds: dict[str, VacancySeed] = {}
        pages_crawled = 0
        listing_pages_parsed = 0
        detail_pages_parsed = 0
        visited_pages: set[str] = set()
        page_queue: list[str] = list(search_urls)
        detail_concurrency = max(1, get_settings().job_parser_detail_concurrency)

        logger.info("site_query_started", site=site, search_urls_count=len(search_urls))

        try:
            while page_queue and pages_crawled < max_pages_safety:
                page_url = page_queue.pop(0)
                if page_url in visited_pages:
                    continue
                visited_pages.add(page_url)
                pages_crawled += 1

                html = await self.fetch_page_text(
                    http_client, page_url, stage="listing", errors=errors
                )
                if html is None:
                    continue

                try:
                    listing = self.parse_listing_page(html, page_url)
                except Exception as exc:
                    errors.append(
                        ScrapeError(stage="listing_parse", url=page_url, message=str(exc))
                    )
                    logger.error(
                        "listing_parse_failed",
                        site=site,
                        page_url=page_url,
                        error=str(exc),
                        exc_info=True,
                    )
                    continue

                logger.info(
                    "listing_page_parsed",
                    site=site,
                    page_url=page_url,
                    vacancies_count=len(listing.vacancies),
                )
                listing_pages_parsed += 1

                for seed in listing.vacancies:
                    canonical_job_url = self._canonical_job_url(seed.job_url)
                    if canonical_job_url not in listing_seeds:
                        listing_seeds[canonical_job_url] = seed.model_copy(
                            update={"job_url": canonical_job_url}
                        )

                if listing.next_page_url and listing.next_page_url not in visited_pages:
                    page_queue.append(listing.next_page_url)

            semaphore = asyncio.Semaphore(detail_concurrency)

            async def enrich_seed(seed: VacancySeed) -> VacancyRecord | None:
                nonlocal detail_pages_parsed

                def finalize_record(record: VacancyRecord | None) -> VacancyRecord | None:
                    if record is None:
                        return None
                    if not self._matches_keyword_policy(record, intent):
                        return None

                    logger.info("detail_enriched", site=site, job_url=record.job_url)
                    return record

                async with semaphore:
                    detail_html = await self.fetch_page_text(
                        http_client,
                        seed.job_url,
                        stage="detail",
                        errors=errors,
                    )
                    if detail_html is None:
                        return finalize_record(self.build_fallback_record(seed))

                    try:
                        detail = self.parse_job_detail_page(detail_html, seed.job_url, seed)
                    except Exception as exc:
                        errors.append(
                            ScrapeError(stage="detail_parse", url=seed.job_url, message=str(exc))
                        )
                        logger.error(
                            "detail_parse_failed",
                            site=site,
                            job_url=seed.job_url,
                            error=str(exc),
                            exc_info=True,
                        )
                        return finalize_record(self.build_fallback_record(seed))

                    detail_pages_parsed += 1

                    company = None
                    company_url = detail.company_url or seed.company_url
                    if company_url:
                        company_html = await self.fetch_page_text(
                            http_client,
                            company_url,
                            stage="company",
                            errors=errors,
                        )
                        if company_html is not None:
                            try:
                                company = self.parse_company_page(company_html, company_url)
                            except Exception as exc:
                                errors.append(
                                    ScrapeError(
                                        stage="company_parse",
                                        url=company_url,
                                        message=str(exc),
                                    )
                                )
                                logger.error(
                                    "company_parse_failed",
                                    site=site,
                                    company_url=company_url,
                                    error=str(exc),
                                    exc_info=True,
                                )

                    record = self._build_record(seed=seed, detail=detail, company=company)
                    return finalize_record(record)

            enriched_records = await asyncio.gather(
                *(enrich_seed(seed) for seed in listing_seeds.values())
            )
            records = [record for record in enriched_records if record is not None]

            duration_seconds = time.perf_counter() - start_ts
            logger.info(
                "query_scrape_completed",
                site=site,
                vacancies_count=len(records),
                errors_count=len(errors),
                pages_crawled=pages_crawled,
                listing_pages_parsed=listing_pages_parsed,
                detail_pages_parsed=detail_pages_parsed,
                duration_seconds=round(duration_seconds, 3),
            )

            status = "ok"
            if not records and errors:
                if listing_pages_parsed == 0:
                    status = "failed"
                elif listing_seeds and detail_pages_parsed == 0:
                    status = "failed"
            return ScrapeRunResult(
                site=site,
                status=status,
                query_plan=query_plan,
                vacancies=records,
                errors=errors,
                pages_crawled=pages_crawled,
            )
        finally:
            if own_client:
                await http_client.aclose()

    def _build_record(
        self,
        *,
        seed: VacancySeed,
        detail: VacancyDetail,
        company: CompanyDetail | None,
    ) -> VacancyRecord:
        skill_values = detail.skills or []
        company_contacts = detail.company_contacts or []
        company_about = detail.company_about
        if company is not None:
            if not company_about:
                company_about = company.company_about
            if not company_contacts:
                company_contacts = company.company_contacts
            if not skill_values:
                skill_values = company.skills

        raw_meta: dict[str, Any] = {}
        raw_meta.update(seed.raw_meta)
        raw_meta.update(detail.raw_meta)
        if company is not None:
            raw_meta.update(company.raw_meta)

        return VacancyRecord(
            site=self.site_code(),
            job_url=self._canonical_job_url(seed.job_url),
            title=detail.title or seed.title,
            company_name=detail.company_name or seed.company_name,
            location=detail.location or seed.location,
            salary_text=detail.salary_text or seed.salary_text,
            salary_min=detail.salary_min,
            salary_max=detail.salary_max,
            currency=detail.currency,
            employment_type=detail.employment_type,
            published_at=detail.published_at or seed.published_at,
            description=detail.description,
            skills=skill_values,
            apply_url=detail.apply_url,
            company_url=detail.company_url or seed.company_url,
            company_about=company_about,
            company_contacts=company_contacts,
            raw_meta=raw_meta,
        )

    @staticmethod
    def _canonical_job_url(url: str) -> str:
        url_no_fragment, _ = urldefrag(url.strip())
        parts = urlsplit(url_no_fragment)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    @staticmethod
    def _matches_keyword_policy(record: VacancyRecord, intent: SearchIntent) -> bool:
        haystack = " ".join(
            [
                record.title or "",
                record.company_name or "",
                record.description or "",
                " ".join(record.skills),
                record.location or "",
            ]
        ).lower()

        for keyword in intent.keywords_include:
            if keyword.lower() not in haystack:
                return False

        for keyword in intent.keywords_exclude:
            if keyword.lower() in haystack:
                return False

        return True
