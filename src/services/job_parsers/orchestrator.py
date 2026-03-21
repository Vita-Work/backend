from __future__ import annotations

import asyncio

import httpx

from src.config import get_settings
from src.services.job_parsers.registry import get_parser, get_registered_parser_names
from src.services.job_parsers.schemas import ScrapeRunResult, SearchIntent


async def run_site_scraper(site_name: str, intent: SearchIntent) -> ScrapeRunResult:
    parser = get_parser(site_name)
    return await parser.scrape_by_intent(intent)


async def run_all_site_scrapers(intent: SearchIntent) -> list[ScrapeRunResult]:
    site_names = get_registered_parser_names()
    if not site_names:
        return []

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        semaphore = asyncio.Semaphore(max(1, get_settings().job_parser_site_concurrency))

        async def run_for_site(site_name: str) -> ScrapeRunResult:
            parser = get_parser(site_name)
            async with semaphore:
                return await parser.scrape_by_intent(intent, client=client)

        return list(await asyncio.gather(*(run_for_site(site_name) for site_name in site_names)))
