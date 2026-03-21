from __future__ import annotations

import json
import re
from datetime import UTC, datetime
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

BASE_URL = "https://www.getonbrd.com"
SEARCH_API_URL = f"{BASE_URL}/api/v0/search/jobs"

_EMPLOYMENT_HINTS = {
    "freelance",
    "full-time",
    "full time",
    "part-time",
    "part time",
    "contract",
    "contractor",
    "permanent",
}


@register_parser("getonbrd")
class GetOnBrdParser(BaseJobParser):
    def site_code(self) -> str:
        return "getonbrd"

    def supports_native_query_search(self) -> bool:
        return True

    def build_search_urls(self, intent: SearchIntent) -> list[str]:
        urls: list[str] = []
        per_page = 20
        for term in self.build_query_terms(intent):
            for lang in ("en", "es"):
                params = {
                    "query": term,
                    "page": 1,
                    "per_page": per_page,
                    "lang": lang,
                }
                urls.append(f"{SEARCH_API_URL}?{urlencode(params)}")
        return sorted(set(urls))

    def parse_listing_page(self, html_text: str, page_url: str) -> ListingPageResult:
        try:
            payload = json.loads(html_text)
        except json.JSONDecodeError as exc:
            raise ValueError("getonbrd_listing_is_not_json") from exc

        vacancies: list[VacancySeed] = []
        for item in payload.get("data", []):
            if not isinstance(item, dict):
                continue

            attributes = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
            links = item.get("links") if isinstance(item.get("links"), dict) else {}
            public_url = _absolute_url(links.get("public_url"))
            if not public_url:
                continue

            min_salary = _to_int(attributes.get("min_salary"))
            max_salary = _to_int(attributes.get("max_salary"))
            salary_text = _format_salary_text(min_salary, max_salary)
            published_at = _unix_to_iso(attributes.get("published_at"))

            vacancies.append(
                VacancySeed(
                    job_url=public_url,
                    title=_to_text(attributes.get("title")),
                    salary_text=salary_text,
                    published_at=published_at,
                    location=_build_api_location(attributes),
                    raw_meta={
                        "source": "search_api",
                        "job_id": item.get("id"),
                        "lang": attributes.get("lang"),
                        "remote": attributes.get("remote"),
                        "remote_modality": attributes.get("remote_modality"),
                        "seniority": _extract_resource_id(attributes.get("seniority")),
                        "modality": _extract_resource_id(attributes.get("modality")),
                    },
                )
            )

        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        current_page = _to_int(meta.get("page")) or _to_int(_query_param(page_url, "page")) or 1
        total_pages = _to_int(meta.get("total_pages")) or current_page
        next_page_url = None
        if current_page < total_pages:
            next_page_url = _replace_query_param(page_url, "page", str(current_page + 1))

        return ListingPageResult(vacancies=vacancies, next_page_url=next_page_url)

    def parse_job_detail_page(
        self, html_text: str, job_url: str, seed: VacancySeed
    ) -> VacancyDetail:
        tree = html.fromstring(html_text)

        title = _extract_best_text(tree.xpath("//h1//text()")) or seed.title
        company_name, company_href = _extract_primary_company_link(tree)

        h2_tokens = _header_tokens(tree)
        location = _extract_location_from_tokens(h2_tokens) or seed.location
        employment_type = _extract_employment_from_tokens(h2_tokens)

        published_at = _first_text(tree.xpath("//time/@datetime")) or seed.published_at
        skills = [
            _clean_text(text) for text in tree.xpath('//a[starts-with(@href, "/jobs/tag/")]/text()')
        ]
        skills = [skill for skill in skills if skill]

        apply_href = _first_text(tree.xpath('//a[contains(@href, "/applications/new")]/@href'))
        apply_url = _absolute_url(apply_href) if apply_href else None

        description_sections = _extract_sections_from_h3(tree)
        description = _build_description(description_sections, tree)

        company_about = None
        for heading in tree.xpath("//h3"):
            heading_text = _clean_text(" ".join(heading.xpath(".//text()"))).lower()
            if heading_text.startswith("about ") or heading_text.startswith("acerca de"):
                company_about = _collect_sibling_text(heading)
                if company_about:
                    break

        return VacancyDetail(
            title=title,
            company_name=company_name or seed.company_name,
            company_url=_absolute_url(company_href) if company_href else seed.company_url,
            location=location,
            salary_text=seed.salary_text,
            employment_type=employment_type,
            published_at=published_at,
            description=description,
            skills=list(dict.fromkeys(skills)),
            apply_url=apply_url,
            company_about=company_about,
            raw_meta={
                "source": "detail_dom",
                "h2_tokens": h2_tokens,
            },
        )

    def parse_company_page(self, html_text: str, company_url: str) -> CompanyDetail | None:
        tree = html.fromstring(html_text)

        company_name = _extract_best_text(tree.xpath("//h1//text()"))

        about_parts = [
            _clean_text(text)
            for text in tree.xpath('//meta[@property="og:description"]/@content')
            if _clean_text(text)
        ]
        company_about = _extract_company_about_from_meta(about_parts[0]) if about_parts else None

        contacts: list[str] = []
        for href in tree.xpath("//a/@href"):
            if not isinstance(href, str):
                continue
            if href.startswith("mailto:"):
                contacts.append(href.replace("mailto:", "").strip())
                continue
            if href.startswith("tel:"):
                contacts.append(href.replace("tel:", "").strip())
                continue
            if href.startswith("http") and "getonbrd.com" not in href:
                contacts.append(href)

        contacts = list(dict.fromkeys(contact for contact in contacts if contact))

        if not company_name and not company_about and not contacts:
            return None

        return CompanyDetail(
            company_name=company_name,
            company_url=company_url,
            company_about=company_about,
            company_contacts=contacts,
            raw_meta={"source": "company_dom"},
        )


def _to_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = _clean_text(value)
        return cleaned or None
    return _clean_text(str(value)) or None


def _clean_text(value: str | None) -> str:
    return " ".join((value or "").split())


def _first_text(values: list[Any]) -> str | None:
    for value in values:
        if not isinstance(value, str):
            continue
        cleaned = _clean_text(value)
        if cleaned:
            return cleaned
    return None


def _extract_best_text(values: list[Any]) -> str | None:
    for value in values:
        if not isinstance(value, str):
            continue
        cleaned = _clean_text(value)
        if not cleaned:
            continue
        if cleaned.startswith("http://") or cleaned.startswith("https://"):
            continue
        if cleaned.lower().endswith((".png", ".jpg", ".jpeg", ".svg")):
            continue
        return cleaned
    return None


def _absolute_url(value: str | None) -> str | None:
    if not value:
        return None
    return urljoin(BASE_URL, value)


def _replace_query_param(url: str, key: str, value: str) -> str:
    parts = urlsplit(url)
    query = parse_qs(parts.query, keep_blank_values=True)
    query[key] = [value]
    new_query = urlencode(query, doseq=True)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))


def _query_param(url: str, key: str) -> str | None:
    return parse_qs(urlsplit(url).query).get(key, [None])[0]


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str):
        digits = re.sub(r"[^0-9]", "", value)
        return int(digits) if digits else None
    return None


def _build_api_location(attributes: dict[str, Any]) -> str | None:
    remote_modality = _to_text(attributes.get("remote_modality"))
    if remote_modality and "remote" in remote_modality:
        if remote_modality == "fully_remote":
            return "Remote"
        return remote_modality.replace("_", " ").title()

    cities = _extract_nested_names(attributes.get("location_cities"))
    regions = _extract_nested_names(attributes.get("location_regions"))
    all_values = [*cities, *regions]
    deduped = list(dict.fromkeys(value for value in all_values if value))
    return ", ".join(deduped) if deduped else None


def _extract_nested_names(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    data = value.get("data")
    if not isinstance(data, list):
        return []

    result: list[str] = []
    for item in data:
        if isinstance(item, dict):
            name = _to_text(item.get("name") or item.get("title"))
            if name:
                result.append(name)
    return result


def _extract_resource_id(value: Any) -> int | None:
    if not isinstance(value, dict):
        return None
    data = value.get("data")
    if not isinstance(data, dict):
        return None
    return _to_int(data.get("id"))


def _format_salary_text(min_salary: int | None, max_salary: int | None) -> str | None:
    if min_salary is None and max_salary is None:
        return None
    if min_salary is not None and max_salary is not None and min_salary != max_salary:
        return f"${min_salary:,} - ${max_salary:,}"
    value = min_salary if min_salary is not None else max_salary
    return f"${value:,}" if value is not None else None


def _unix_to_iso(value: Any) -> str | None:
    timestamp = _to_int(value)
    if timestamp is None:
        return None
    try:
        return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()
    except Exception:
        return None


def _header_tokens(tree: html.HtmlElement) -> list[str]:
    raw_tokens = [_clean_text(text) for text in tree.xpath("//h2//text()")]
    tokens = [token for token in raw_tokens if token and token != "|"]
    return list(dict.fromkeys(tokens))


def _extract_location_from_tokens(tokens: list[str]) -> str | None:
    for token in tokens:
        lowered = token.lower()
        if "remote" in lowered or "hybrid" in lowered or "in-office" in lowered:
            return token
    return tokens[0] if tokens else None


def _extract_employment_from_tokens(tokens: list[str]) -> str | None:
    for token in tokens:
        lowered = token.lower()
        if lowered in _EMPLOYMENT_HINTS:
            return token
    return None


def _extract_sections_from_h3(tree: html.HtmlElement) -> dict[str, str]:
    desired = {
        "funciones",
        "requisitos",
        "deseables",
        "beneficios",
        "functions",
        "requirements",
        "desirable",
        "benefits",
    }
    result: dict[str, str] = {}

    for heading in tree.xpath("//h3"):
        label = _clean_text(" ".join(heading.xpath(".//text()")))
        lowered = label.lower()
        if lowered not in desired:
            continue
        section_text = _collect_sibling_text(heading)
        if section_text:
            result[label] = section_text

    return result


def _collect_sibling_text(node: html.HtmlElement) -> str | None:
    parts: list[str] = []
    for sibling in node.itersiblings():
        if sibling.tag.lower() == "h3":
            break
        text = _clean_text(" ".join(sibling.xpath(".//text()")))
        if text:
            parts.append(text)

    if not parts:
        return None
    return "\n".join(parts)


def _build_description(sections: dict[str, str], tree: html.HtmlElement) -> str | None:
    if sections:
        chunks = [f"{name}:\n{body}" for name, body in sections.items()]
        return "\n\n".join(chunks)

    fallback = _clean_text(" ".join(tree.xpath("//main//text()")))
    return fallback[:8000] if fallback else None


def _extract_company_about_from_meta(meta_description: str) -> str | None:
    cleaned = _clean_text(meta_description)
    if not cleaned:
        return None

    match = re.search(r"About\s+.+?:\s*(.+)", cleaned, flags=re.IGNORECASE)
    if match:
        return _clean_text(match.group(1))

    return cleaned


def _extract_primary_company_link(tree: html.HtmlElement) -> tuple[str | None, str | None]:
    for anchor in tree.xpath('//a[starts-with(@href, "/companies/")]'):
        href = anchor.get("href")
        if not href or "follow_unfollow" in href:
            continue
        name = _extract_best_text(anchor.xpath(".//text()"))
        if not name or name.lower() == "follow":
            continue
        return name, href
    return None, None
