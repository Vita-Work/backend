from __future__ import annotations

from urllib.parse import urljoin

from lxml import html

from src.services.job_parsers.base import BaseJobParser
from src.services.job_parsers.registry import register_parser
from src.services.job_parsers.schemas import (
    CompanyDetail,
    ListingPageResult,
    SearchIntent,
    VacancyDetail,
    VacancySeed,
)

BASE_URL = "https://devkg.com"


@register_parser("devkg")
class DevKgParser(BaseJobParser):
    def site_code(self) -> str:
        return "devkg"

    def supports_native_query_search(self) -> bool:
        return False

    def build_search_urls(self, intent: SearchIntent) -> list[str]:
        return []

    def parse_listing_page(self, html_text: str, page_url: str) -> ListingPageResult:
        tree = html.fromstring(html_text)
        hrefs = tree.xpath('//article//a[starts-with(@href, "/ru/jobs/")]/@href')

        vacancies: list[VacancySeed] = []
        seen: set[str] = set()
        for href in hrefs:
            abs_url = _absolute_url(href)
            if abs_url in seen:
                continue
            seen.add(abs_url)
            vacancies.append(VacancySeed(job_url=abs_url))

        next_href = _first(tree.xpath('//link[@rel="next"]/@href'))
        next_page_url = _absolute_url(next_href) if next_href else None

        return ListingPageResult(vacancies=vacancies, next_page_url=next_page_url)

    def parse_job_detail_page(
        self, html_text: str, job_url: str, seed: VacancySeed
    ) -> VacancyDetail:
        tree = html.fromstring(html_text)
        title = _first(tree.xpath("//h1/text()"))
        company_href = _first(tree.xpath('//a[starts-with(@href, "/ru/organizations/")]/@href'))
        company_name = _first(tree.xpath('//a[starts-with(@href, "/ru/organizations/")]/text()'))
        description_parts = tree.xpath("//main//text()")
        description = _clean(" ".join(description_parts)) if description_parts else None

        return VacancyDetail(
            title=title or seed.title,
            company_name=company_name or seed.company_name,
            company_url=_absolute_url(company_href) if company_href else seed.company_url,
            description=description,
        )

    def parse_company_page(self, html_text: str, company_url: str) -> CompanyDetail | None:
        tree = html.fromstring(html_text)
        name = _first(tree.xpath("//h1/text()"))
        about = _first(tree.xpath("//main//p/text()"))

        return CompanyDetail(
            company_name=name,
            company_url=company_url,
            company_about=about,
        )


def _absolute_url(value: str | None) -> str | None:
    if not value:
        return None
    return urljoin(BASE_URL, value)


def _first(values: list[str]) -> str | None:
    for value in values:
        cleaned = _clean(value)
        if cleaned:
            return cleaned
    return None


def _clean(value: str | None) -> str:
    return " ".join((value or "").split())
