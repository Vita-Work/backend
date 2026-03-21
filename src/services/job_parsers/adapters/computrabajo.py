from __future__ import annotations

import json
import re
import unicodedata
from typing import Any
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit

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

BASE_URL = "https://mx.computrabajo.com"

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-MX,es;q=0.9,en-US;q=0.8,en;q=0.7",
}


@register_parser("computrabajo")
class ComputrabajoParser(BaseJobParser):
    def site_code(self) -> str:
        return "computrabajo"

    def supports_native_query_search(self) -> bool:
        return True

    def build_request_headers(self, stage: str) -> dict[str, str]:
        return _BROWSER_HEADERS

    def build_search_urls(self, intent: SearchIntent) -> list[str]:
        urls: list[str] = []
        for term in self.build_query_terms(intent):
            slug = _slugify_term(term)
            if not slug:
                continue
            urls.append(f"{BASE_URL}/trabajo-de-{slug}")
        return sorted(set(urls))

    def parse_listing_page(self, html_text: str, page_url: str) -> ListingPageResult:
        tree = html.fromstring(html_text)
        jsonld_vacancies = self._extract_listing_from_jsonld(html_text)
        dom_vacancies = self._extract_listing_from_dom(tree)
        vacancies = _merge_listing_seeds(primary=jsonld_vacancies, fallback=dom_vacancies)

        next_page_url = _first_text(
            tree.xpath(
                '//span[contains(@class, "buildLink") and '
                'contains(normalize-space(.), "Siguiente")]/@data-path'
            )
        )
        if not next_page_url:
            next_page_url = _first_text(
                tree.xpath('//a[contains(normalize-space(.), "Siguiente")]/@href')
            )

        return ListingPageResult(
            vacancies=vacancies,
            next_page_url=_absolute_url(next_page_url) if next_page_url else None,
        )

    def parse_job_detail_page(
        self,
        html_text: str,
        job_url: str,
        seed: VacancySeed,
    ) -> VacancyDetail:
        tree = html.fromstring(html_text)
        job_posting = _extract_job_posting_from_jsonld(html_text)
        if job_posting is not None:
            salary_min, salary_max, currency, salary_text = _extract_jsonld_salary(job_posting)
            keywords = _extract_keywords(job_posting.get("keywords"))
            return VacancyDetail(
                title=job_posting.get("title") or seed.title,
                company_name=_jsonld_company_name(job_posting) or seed.company_name,
                company_url=_jsonld_company_url(job_posting) or seed.company_url,
                location=_extract_jsonld_location(job_posting) or seed.location,
                salary_text=salary_text or seed.salary_text,
                salary_min=salary_min,
                salary_max=salary_max,
                currency=currency,
                employment_type=_normalize_employment_type(job_posting.get("employmentType")),
                published_at=job_posting.get("datePosted") or seed.published_at,
                description=_to_text(job_posting.get("description")),
                skills=keywords,
                apply_url=_extract_apply_url(tree),
                raw_meta={"source": "jsonld", "jobposting_id": job_posting.get("identifier")},
            )

        title = _first_text(tree.xpath("//h1/text()")) or seed.title
        company_name = (
            _first_text(
                tree.xpath('//a[contains(@href, "/empresas/ofertas-de-trabajo-de")]/text()')
            )
            or seed.company_name
        )
        company_href = _first_text(
            tree.xpath('//a[contains(@href, "/empresas/ofertas-de-trabajo-de")]/@href')
        )
        description = _extract_description_from_dom(tree)
        salary_text = _extract_salary_text(tree) or seed.salary_text
        location = _extract_location_from_dom(tree) or seed.location
        published_at = _extract_published_text(tree) or seed.published_at

        return VacancyDetail(
            title=title,
            company_name=company_name,
            company_url=_absolute_url(company_href) if company_href else seed.company_url,
            location=location,
            salary_text=salary_text,
            published_at=published_at,
            description=description,
            skills=_extract_dom_keywords(tree),
            apply_url=_extract_apply_url(tree),
            raw_meta={"source": "dom"},
        )

    def parse_company_page(self, html_text: str, company_url: str) -> CompanyDetail | None:
        tree = html.fromstring(html_text)
        company_name = _first_text(tree.xpath("//h1/text()"))

        about = _first_text(
            tree.xpath(
                '//*[contains(translate(normalize-space(.), "LAEMPRESA", "laempresa"), '
                '"la empresa")]/following::p[1]//text()'
            )
        )
        if not about:
            paragraphs = [_clean_text(text) for text in tree.xpath("//main//p//text()")]
            paragraphs = [text for text in paragraphs if len(text) > 40]
            about = "\n".join(paragraphs[:4]) if paragraphs else None

        contacts: list[str] = []
        for href in tree.xpath('//a[starts-with(@href, "mailto:")]/@href'):
            contacts.append(href.replace("mailto:", "").strip())
        for href in tree.xpath('//a[starts-with(@href, "tel:")]/@href'):
            contacts.append(href.replace("tel:", "").strip())
        for href in tree.xpath("//a/@href"):
            if href.startswith("http") and "computrabajo.com" not in href:
                contacts.append(href)

        contacts = list(dict.fromkeys(contact for contact in contacts if contact))

        if not company_name and not about and not contacts:
            return None

        return CompanyDetail(
            company_name=company_name,
            company_url=company_url,
            company_about=about,
            company_contacts=contacts,
            raw_meta={"source": "dom"},
        )

    def _extract_listing_from_jsonld(self, html_text: str) -> list[VacancySeed]:
        vacancies: list[VacancySeed] = []
        seen: set[str] = set()

        for item in _extract_itemlist_items(html_text):
            url = _absolute_url(item.get("url"))
            if not url or url in seen:
                continue
            seen.add(url)

            company = item.get("hiringOrganization") if isinstance(item, dict) else {}
            location = _extract_jsonld_location(item) if isinstance(item, dict) else None
            vacancies.append(
                VacancySeed(
                    job_url=url,
                    title=_to_text(item.get("name")) if isinstance(item, dict) else None,
                    company_name=(company.get("name") if isinstance(company, dict) else None),
                    company_url=(
                        _absolute_url(company.get("url"))
                        if isinstance(company, dict) and company.get("url")
                        else None
                    ),
                    location=location,
                    raw_meta={"source": "jsonld_itemlist"},
                )
            )

        return vacancies

    def _extract_listing_from_dom(self, tree: html.HtmlElement) -> list[VacancySeed]:
        vacancies: list[VacancySeed] = []
        seen: set[str] = set()

        for article in tree.xpath("//article"):
            job_href = _first_text(
                article.xpath(
                    ".//h2//a[contains(@href, "
                    '"/ofertas-de-trabajo/oferta-de-trabajo-de")][1]/@href | '
                    './/a[contains(@href, "/ofertas-de-trabajo/oferta-de-trabajo-de")][1]/@href'
                )
            )
            job_url = _canonical_url(_absolute_url(job_href)) if job_href else None
            if not job_url or job_url in seen:
                continue
            seen.add(job_url)

            title = _first_text(article.xpath(".//h2//a//text()"))
            company_name = _first_text(
                article.xpath('.//a[contains(@href, "/empresas/ofertas-de-trabajo-de")]/text()')
            )
            company_url = _first_text(
                article.xpath('.//a[contains(@href, "/empresas/ofertas-de-trabajo-de")]/@href')
            )
            published_at = _extract_published_text(article)
            salary_text = _extract_salary_text(article)
            location = _extract_location_from_dom(article)

            vacancies.append(
                VacancySeed(
                    job_url=job_url,
                    title=title,
                    company_name=company_name,
                    company_url=_absolute_url(company_url) if company_url else None,
                    published_at=published_at,
                    salary_text=salary_text,
                    location=location,
                    raw_meta={"source": "dom_article"},
                )
            )

        return vacancies


def _extract_itemlist_items(html_text: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for payload in _iter_jsonld_payloads(html_text):
        type_values = _jsonld_types(payload)
        if "ItemList" not in type_values:
            continue

        item_list = payload.get("itemListElement")
        if not isinstance(item_list, list):
            continue

        for element in item_list:
            if isinstance(element, dict):
                item = element.get("item", element)
                if isinstance(item, dict):
                    items.append(item)
                elif isinstance(item, str):
                    items.append({"url": item})
            elif isinstance(element, str):
                items.append({"url": element})

    return items


def _extract_job_posting_from_jsonld(html_text: str) -> dict[str, Any] | None:
    for payload in _iter_jsonld_payloads(html_text):
        if "JobPosting" in _jsonld_types(payload):
            return payload
    return None


def _iter_jsonld_payloads(html_text: str) -> list[dict[str, Any]]:
    tree = html.fromstring(html_text)
    payloads: list[dict[str, Any]] = []
    for raw in tree.xpath('//script[@type="application/ld+json"]/text()'):
        script_text = (raw or "").strip()
        if not script_text:
            continue
        try:
            data = json.loads(script_text)
        except Exception:
            continue
        payloads.extend(_flatten_jsonld(data))
    return payloads


def _flatten_jsonld(data: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if isinstance(data, dict):
        items.append(data)
        graph = data.get("@graph")
        if isinstance(graph, list):
            for node in graph:
                items.extend(_flatten_jsonld(node))
    elif isinstance(data, list):
        for node in data:
            items.extend(_flatten_jsonld(node))
    return items


def _jsonld_types(payload: dict[str, Any]) -> set[str]:
    raw_type = payload.get("@type")
    if isinstance(raw_type, str):
        return {raw_type}
    if isinstance(raw_type, list):
        return {value for value in raw_type if isinstance(value, str)}
    return set()


def _jsonld_company_name(job_posting: dict[str, Any]) -> str | None:
    company = job_posting.get("hiringOrganization")
    if isinstance(company, dict):
        return _to_text(company.get("name"))
    return None


def _jsonld_company_url(job_posting: dict[str, Any]) -> str | None:
    company = job_posting.get("hiringOrganization")
    if not isinstance(company, dict):
        return None
    return _absolute_url(company.get("url") or company.get("sameAs"))


def _extract_jsonld_location(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None

    locations = payload.get("jobLocation")
    if isinstance(locations, dict):
        locations = [locations]

    if not isinstance(locations, list):
        return None

    result: list[str] = []
    for location in locations:
        if not isinstance(location, dict):
            continue
        address = location.get("address")
        if isinstance(address, dict):
            parts = [
                _to_text(address.get("addressLocality")),
                _to_text(address.get("addressRegion")),
                _to_text(address.get("addressCountry")),
            ]
            joined = ", ".join(part for part in parts if part)
            if joined:
                result.append(joined)

    return " | ".join(dict.fromkeys(result)) if result else None


def _extract_jsonld_salary(
    job_posting: dict[str, Any],
) -> tuple[int | None, int | None, str | None, str | None]:
    base_salary = job_posting.get("baseSalary")
    if not isinstance(base_salary, dict):
        return None, None, None, None

    currency = _to_text(base_salary.get("currency"))
    salary_value = base_salary.get("value")
    if not isinstance(salary_value, dict):
        amount = _to_int(base_salary.get("value"))
        if amount is None:
            return None, None, currency, None
        return amount, amount, currency, _format_salary_text(amount, amount, currency)

    minimum = _to_int(salary_value.get("minValue") or salary_value.get("value"))
    maximum = _to_int(salary_value.get("maxValue") or salary_value.get("value"))
    if minimum is None and maximum is None:
        return None, None, currency, None

    return minimum, maximum, currency, _format_salary_text(minimum, maximum, currency)


def _extract_salary_text(tree: html.HtmlElement) -> str | None:
    candidates = [
        _clean_text(text)
        for text in tree.xpath(".//text()[contains(., '$') or contains(., 'A convenir')]")
    ]
    for candidate in candidates:
        if candidate:
            return candidate
    return None


def _extract_published_text(tree: html.HtmlElement) -> str | None:
    candidates = [_clean_text(text) for text in tree.xpath('.//text()[contains(., "Hace ")]')]
    for candidate in candidates:
        if candidate:
            return candidate
    return None


def _extract_location_from_dom(tree: html.HtmlElement) -> str | None:
    paragraph_texts = [_clean_text(text) for text in tree.xpath(".//p//text()")]
    candidates: list[tuple[int, str]] = []

    for text in paragraph_texts:
        if not text:
            continue
        if "$" in text or "A convenir" in text or "Hace " in text:
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?", text):
            continue
        if not any(char.isalpha() for char in text):
            continue
        if len(text) < 3:
            continue

        score = 0
        lowered = text.lower()
        if "," in text:
            score += 2
        if any(
            token in lowered for token in ("remote", "remoto", "híbrido", "hybrid", "presencial")
        ):
            score += 2
        if re.search(r"\d", text):
            score -= 2
        candidates.append((score, text))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _extract_apply_url(tree: html.HtmlElement) -> str | None:
    href = _first_text(
        tree.xpath(
            '//a[contains(normalize-space(translate(., "POSTULARME", "postularme")), '
            '"postularme")]/@href'
        )
    )
    return _absolute_url(href) if href else None


def _extract_description_from_dom(tree: html.HtmlElement) -> str | None:
    description_chunks: list[str] = []

    section_nodes = tree.xpath(
        '//*[contains(translate(normalize-space(.), "DESCRIPCIÓN", "descripción"), '
        '"descripción de la oferta")]/following::*'
    )
    for node in section_nodes[:120]:
        text = _clean_text(" ".join(node.xpath(".//text()")))
        if text:
            description_chunks.append(text)
        if "Requerimientos" in text or "Palabras clave" in text:
            break

    if description_chunks:
        return "\n".join(dict.fromkeys(description_chunks))

    main_text = _clean_text(" ".join(tree.xpath("//main//text()")))
    return main_text[:6000] if main_text else None


def _extract_dom_keywords(tree: html.HtmlElement) -> list[str]:
    candidates = [
        _clean_text(text) for text in tree.xpath('//a[contains(@href, "trabajo-de-")]/text()')
    ]
    skills = [candidate for candidate in candidates if candidate and len(candidate) <= 40]
    return list(dict.fromkeys(skills[:15]))


def _normalize_employment_type(raw_value: Any) -> str | None:
    if isinstance(raw_value, str):
        return _clean_text(raw_value)
    if isinstance(raw_value, list):
        values = [_clean_text(value) for value in raw_value if isinstance(value, str)]
        values = [value for value in values if value]
        return " | ".join(values) if values else None
    return None


def _extract_keywords(raw_value: Any) -> list[str]:
    if isinstance(raw_value, str):
        parts = [_clean_text(part) for part in raw_value.split(",")]
        return [part for part in parts if part]
    if isinstance(raw_value, list):
        values = [_clean_text(part) for part in raw_value if isinstance(part, str)]
        return [value for value in values if value]
    return []


def _merge_listing_seeds(
    primary: list[VacancySeed], fallback: list[VacancySeed]
) -> list[VacancySeed]:
    if not primary:
        return fallback
    if not fallback:
        return primary

    fallback_by_url = {_canonical_url(seed.job_url): seed for seed in fallback}
    merged: list[VacancySeed] = []
    for seed in primary:
        fallback_seed = fallback_by_url.get(_canonical_url(seed.job_url))
        if fallback_seed is None:
            merged.append(seed)
            continue
        merged.append(
            seed.model_copy(
                update={
                    "title": seed.title or fallback_seed.title,
                    "company_name": seed.company_name or fallback_seed.company_name,
                    "company_url": seed.company_url or fallback_seed.company_url,
                    "published_at": seed.published_at or fallback_seed.published_at,
                    "salary_text": seed.salary_text or fallback_seed.salary_text,
                    "location": seed.location or fallback_seed.location,
                    "raw_meta": {**fallback_seed.raw_meta, **seed.raw_meta},
                }
            )
        )
    return merged


def _slugify_term(term: str) -> str:
    normalized = unicodedata.normalize("NFKD", term)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_value = ascii_value.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value)
    return slug.strip("-")


def _canonical_url(value: str | None) -> str:
    url_no_fragment, _ = urldefrag((value or "").strip())
    parts = urlsplit(url_no_fragment)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


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


def _to_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return _clean_text(value)
    return _clean_text(str(value))


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str):
        digits = re.sub(r"[^0-9]", "", value)
        return int(digits) if digits else None
    return None


def _format_salary_text(
    minimum: int | None, maximum: int | None, currency: str | None
) -> str | None:
    if minimum is None and maximum is None:
        return None
    if minimum is not None and maximum is not None and minimum != maximum:
        middle = f"{minimum:,} - {maximum:,}"
    else:
        middle = f"{(minimum or maximum or 0):,}"
    return f"{middle} {currency}".strip()
