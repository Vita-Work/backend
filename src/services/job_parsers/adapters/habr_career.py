from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

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

BASE_URL = "https://career.habr.com"
_SSR_STATE_PATTERN = re.compile(
    r'<script type="application/json" data-ssr-state="true">(.*?)</script>',
    re.DOTALL,
)


@register_parser("habr_career")
class HabrCareerParser(BaseJobParser):
    def site_code(self) -> str:
        return "habr_career"

    def supports_native_query_search(self) -> bool:
        return True

    def build_search_urls(self, intent: SearchIntent) -> list[str]:
        urls: list[str] = []
        for term in self.build_query_terms(intent):
            params = {"type": "all", "q": term}
            urls.append(f"{BASE_URL}/vacancies?{urlencode(params)}")
        return sorted(set(urls))

    def parse_listing_page(self, html_text: str, page_url: str) -> ListingPageResult:
        state = _extract_ssr_state(html_text)
        if state:
            return self._parse_listing_from_state(state, page_url)
        return self._parse_listing_from_dom(html_text, page_url)

    def parse_job_detail_page(
        self, html_text: str, job_url: str, seed: VacancySeed
    ) -> VacancyDetail:
        state = _extract_ssr_state(html_text)
        if state and state.get("vacancy"):
            vacancy = state["vacancy"]
            company = state.get("company") or vacancy.get("company") or {}
            salary = vacancy.get("salary") or {}
            predicted = vacancy.get("predictedSalary") or {}
            locations = vacancy.get("locations") or []
            location = (
                ", ".join(loc.get("title", "") for loc in locations if loc.get("title")) or None
            )
            if not location:
                location = vacancy.get("humanCityNames")
            description_html = vacancy.get("description") or ""
            description = (
                _clean_text(html.fromstring(description_html).text_content())
                if description_html
                else None
            )
            skills = [
                item.get("title", "") for item in vacancy.get("skills", []) if item.get("title")
            ]

            return VacancyDetail(
                title=vacancy.get("title") or seed.title,
                company_name=company.get("name") or company.get("title") or seed.company_name,
                company_url=_absolute_url(company.get("href") or seed.company_url),
                location=location,
                salary_text=salary.get("formatted")
                or predicted.get("formatted")
                or seed.salary_text,
                salary_min=salary.get("from") or predicted.get("from"),
                salary_max=salary.get("to") or predicted.get("to"),
                currency=(salary.get("currency") or predicted.get("currency")),
                employment_type=vacancy.get("employmentType") or vacancy.get("employment"),
                published_at=(vacancy.get("publishedDate") or {}).get("date") or seed.published_at,
                description=description,
                skills=skills,
                apply_url=_extract_apply_url(html_text, job_url, vacancy.get("id")),
                company_about=company.get("description"),
                raw_meta={
                    "vacancy_id": vacancy.get("id"),
                    "qualification": vacancy.get("qualification"),
                },
            )

        return self._parse_detail_from_dom(html_text, job_url, seed)

    def parse_company_page(self, html_text: str, company_url: str) -> CompanyDetail | None:
        tree = html.fromstring(html_text)

        company_name = _first_text(tree.xpath('//div[contains(@class, "company_name")]/a/text()'))
        if not company_name:
            heading = _first_text(tree.xpath("//h1/text()"))
            if heading:
                company_name = heading.replace("О компании «", "").replace("»", "").strip()

        company_about = _first_text(tree.xpath('//div[contains(@class, "company_about")]/text()'))
        if not company_about:
            company_about = _first_text(
                tree.xpath('//div[contains(@class, "about_company")]//p/text()')
            )

        skills = [_clean_text(text) for text in tree.xpath('//a[contains(@class, "skill")]/text()')]
        skills = [value for value in skills if value]

        contacts = [
            _clean_text(text)
            for text in tree.xpath('//div[contains(@class, "contacts")]//a/text()')
            + tree.xpath(
                '//div[contains(@class, "contacts")]//div[contains(@class, "value")]/text()'
            )
            if _clean_text(text)
        ]

        state = _extract_ssr_state(html_text)
        if state:
            for member in state.get("publicMembers", []):
                full_name = member.get("fullName")
                position = member.get("position")
                if full_name and position:
                    contacts.append(f"{full_name} ({position})")
                elif full_name:
                    contacts.append(full_name)

        return CompanyDetail(
            company_name=company_name,
            company_url=company_url,
            company_about=company_about,
            company_contacts=list(dict.fromkeys(contacts)),
            skills=list(dict.fromkeys(skills)),
        )

    def _parse_listing_from_state(self, state: dict[str, Any], page_url: str) -> ListingPageResult:
        vacancies: list[VacancySeed] = []

        vacancies_payload = state.get("vacancies", [])
        if isinstance(vacancies_payload, dict):
            vacancy_items = vacancies_payload.get("items")
            if vacancy_items is None:
                vacancy_items = vacancies_payload.get("list", [])
            pagination_meta = vacancies_payload.get("meta") or {}
        else:
            vacancy_items = vacancies_payload
            pagination_meta = state.get("meta") or {}

        for item in vacancy_items:
            if not isinstance(item, dict):
                continue
            href = item.get("href")
            if not href:
                continue

            company = item.get("company") or {}
            salary = item.get("salary") or {}
            predicted = item.get("predictedSalary") or {}
            locations = item.get("locations") or []
            location = (
                ", ".join(loc.get("title", "") for loc in locations if loc.get("title")) or None
            )

            vacancies.append(
                VacancySeed(
                    job_url=_absolute_url(href),
                    title=item.get("title"),
                    company_name=company.get("title") or company.get("name"),
                    company_url=_absolute_url(company.get("href")) if company.get("href") else None,
                    published_at=(item.get("publishedDate") or {}).get("date"),
                    salary_text=salary.get("formatted") or predicted.get("formatted"),
                    location=location,
                    raw_meta={
                        "vacancy_id": item.get("id"),
                        "qualification": item.get("qualification"),
                    },
                )
            )

        current_page = int(pagination_meta.get("currentPage") or 1)
        total_pages = int(pagination_meta.get("totalPages") or 1)
        next_page_url = None
        if current_page < total_pages:
            next_page_url = _replace_query_param(page_url, "page", str(current_page + 1))

        return ListingPageResult(vacancies=vacancies, next_page_url=next_page_url)

    def _parse_listing_from_dom(self, html_text: str, page_url: str) -> ListingPageResult:
        tree = html.fromstring(html_text)
        vacancies: list[VacancySeed] = []

        hrefs = tree.xpath(
            '//a[contains(@class, "vacancy-card__title-link")]/@href | '
            '//a[contains(@class, "vacancy-card__backdrop-link")]/@href'
        )
        seen: set[str] = set()
        for href in hrefs:
            url = _absolute_url(href)
            if url in seen:
                continue
            seen.add(url)
            vacancies.append(VacancySeed(job_url=url))

        next_href = _first_text(tree.xpath('//a[contains(@class, "next_page")]/@href'))
        next_page_url = _absolute_url(next_href) if next_href else None

        return ListingPageResult(vacancies=vacancies, next_page_url=next_page_url)

    def _parse_detail_from_dom(
        self, html_text: str, job_url: str, seed: VacancySeed
    ) -> VacancyDetail:
        tree = html.fromstring(html_text)
        title = _first_text(tree.xpath("//h1/text()")) or seed.title
        company_href = _first_text(tree.xpath('//a[starts-with(@href, "/companies/")]/@href'))
        company_name = _first_text(tree.xpath('//a[starts-with(@href, "/companies/")]/text()'))
        description_parts = tree.xpath('//div[contains(@class, "vacancy-description")]//text()')
        description = _clean_text(" ".join(description_parts)) if description_parts else None
        skills = [
            _clean_text(value)
            for value in tree.xpath('//div[contains(@class, "chip-without-icon__text")]/text()')
        ]
        skills = [value for value in skills if value]

        return VacancyDetail(
            title=title,
            company_name=company_name or seed.company_name,
            company_url=_absolute_url(company_href) if company_href else seed.company_url,
            description=description,
            skills=skills,
            apply_url=_extract_apply_url(html_text, job_url, None),
        )


def _extract_ssr_state(html_text: str) -> dict[str, Any] | None:
    match = _SSR_STATE_PATTERN.search(html_text)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _absolute_url(value: str | None) -> str | None:
    if not value:
        return None
    return urljoin(BASE_URL, value)


def _first_text(values: list[str]) -> str | None:
    for value in values:
        cleaned = _clean_text(value)
        if cleaned:
            return cleaned
    return None


def _clean_text(value: str | None) -> str:
    return " ".join((value or "").split())


def _replace_query_param(url: str, key: str, value: str) -> str:
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    query[key] = [value]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query, doseq=True), ""))


def _extract_apply_url(html_text: str, job_url: str, vacancy_id: int | None) -> str | None:
    tree = html.fromstring(html_text)
    href = _first_text(tree.xpath('//a[contains(text(), "Откликнуться")]/@href'))
    if href:
        return _absolute_url(href)
    if vacancy_id is not None:
        return f"{BASE_URL}/users/auth/tmid/vacancy/{vacancy_id}/response"
    return job_url
