from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

import httpx
from lxml import html

from src.logger import get_logger
from src.services.job_parsers.base import BaseJobParser
from src.services.job_parsers.registry import register_parser
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

BASE_API_URL = "https://api.hh.ru"
SEARCH_URL = f"{BASE_API_URL}/vacancies"
AREA_SUGGEST_URL = f"{BASE_API_URL}/suggests/areas"
HH_HOST = "hh.ru"
HH_USER_AGENT = "VitaBot/1.0 (contact@vita.local)"

logger = get_logger("services.job_parsers.hh")


@register_parser("hh")
class HHParser(BaseJobParser):
    def __init__(self) -> None:
        self._request_semaphore = asyncio.Semaphore(2)

    def site_code(self) -> str:
        return "hh"

    def supports_native_query_search(self) -> bool:
        return True

    def build_request_headers(self, stage: str) -> dict[str, str]:
        return {
            "HH-User-Agent": HH_USER_AGENT,
            "Accept": "application/json",
        }

    def build_search_urls(self, intent: SearchIntent) -> list[str]:
        urls: list[str] = []
        for term in self.build_query_terms(intent):
            params = self._build_search_params(query_term=term, area_ids=(), intent=intent, page=0)
            urls.append(f"{SEARCH_URL}?{urlencode(params, doseq=True)}")
        return sorted(set(urls))

    async def scrape_by_intent(
        self,
        intent: SearchIntent,
        *,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 20.0,
        max_pages_safety: int = 100,
    ) -> ScrapeRunResult:
        query_terms = self.build_query_terms(intent)
        site = self.site_code()

        if not query_terms:
            query_plan = SiteQueryPlan(site=site, terms=[], search_urls=[])
            return ScrapeRunResult(
                site=site,
                status="failed",
                query_plan=query_plan,
                errors=[ScrapeError(stage="query_plan", message="no_search_terms_built")],
            )

        own_client = client is None
        http_client = client or httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True)

        try:
            area_ids, resolution_errors = await self._resolve_area_ids(
                http_client, intent.locations
            )
            if resolution_errors:
                query_plan = SiteQueryPlan(site=site, terms=query_terms, search_urls=[])
                return ScrapeRunResult(
                    site=site,
                    status="failed",
                    query_plan=query_plan,
                    errors=resolution_errors,
                )

            search_urls = []
            for term in query_terms:
                params = self._build_search_params(term, area_ids, intent, page=0)
                search_urls.append(f"{SEARCH_URL}?{urlencode(params, doseq=True)}")
            query_plan = SiteQueryPlan(
                site=site,
                terms=query_terms,
                search_urls=sorted(set(search_urls)),
            )

            if not query_plan.search_urls:
                return ScrapeRunResult(
                    site=site,
                    status="failed",
                    query_plan=query_plan,
                    errors=[ScrapeError(stage="query_plan", message="no_search_urls_built")],
                )

            return await self._scrape_from_query_plan(
                intent,
                query_plan=query_plan,
                client=http_client,
                timeout_seconds=timeout_seconds,
                max_pages_safety=max_pages_safety,
            )
        finally:
            if own_client:
                await http_client.aclose()

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
            async with self._request_semaphore:
                response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code == 403 and stage == "listing":
                message = "captcha_required"
            elif status_code == 429 and stage in {"detail", "company"}:
                message = "rate_limit_exceeded"
            else:
                message = str(exc)

            errors.append(ScrapeError(stage=stage, url=url, message=message))
            logger.error(
                "http_request_failed",
                site=self.site_code(),
                stage=stage,
                url=url,
                error=message,
            )
            return None
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

    def parse_listing_page(self, html_text: str, page_url: str) -> ListingPageResult:
        payload = _load_json_payload(html_text, stage="listing")

        vacancies: list[VacancySeed] = []
        for item in payload.get("items", []):
            if not isinstance(item, dict):
                continue

            api_url = _to_text(item.get("url"))
            alternate_url = _to_text(item.get("alternate_url"))
            if not api_url:
                continue

            employer = item.get("employer") if isinstance(item.get("employer"), dict) else {}
            snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
            vacancies.append(
                VacancySeed(
                    job_url=api_url,
                    title=_to_text(item.get("name")),
                    company_name=_to_text(employer.get("name")),
                    company_url=_to_text(employer.get("url")),
                    published_at=_to_text(item.get("published_at")),
                    salary_text=_format_salary_text(item.get("salary"), item.get("salary_range")),
                    location=_extract_location(item),
                    raw_meta={
                        "alternate_url": alternate_url,
                        "apply_alternate_url": _to_text(item.get("apply_alternate_url")),
                        "public_company_url": _to_text(employer.get("alternate_url")),
                        "schedule": _extract_named_value(item.get("schedule")),
                        "employment": _extract_named_value(item.get("employment")),
                        "employment_form": _extract_named_value(item.get("employment_form")),
                        "work_format": _extract_named_value(item.get("work_format")),
                        "snippet": {
                            "requirement": _to_text(snippet.get("requirement")),
                            "responsibility": _to_text(snippet.get("responsibility")),
                        },
                    },
                )
            )

        current_page = _to_int(payload.get("page")) or _to_int(_query_param(page_url, "page")) or 0
        total_pages = _to_int(payload.get("pages")) or 0
        next_page_url = None
        if current_page + 1 < total_pages:
            next_page_url = _replace_query_param(page_url, "page", str(current_page + 1))

        return ListingPageResult(vacancies=vacancies, next_page_url=next_page_url)

    def parse_job_detail_page(
        self, html_text: str, job_url: str, seed: VacancySeed
    ) -> VacancyDetail:
        payload = _load_json_payload(html_text, stage="detail")
        employer = payload.get("employer") if isinstance(payload.get("employer"), dict) else {}

        return VacancyDetail(
            title=_to_text(payload.get("name")) or seed.title,
            company_name=_to_text(employer.get("name")) or seed.company_name,
            company_url=_to_text(employer.get("url")) or seed.company_url,
            location=_extract_location(payload) or seed.location,
            salary_text=_format_salary_text(payload.get("salary"), payload.get("salary_range"))
            or seed.salary_text,
            salary_min=_extract_salary_bound(
                payload.get("salary"),
                payload.get("salary_range"),
                "from",
            ),
            salary_max=_extract_salary_bound(
                payload.get("salary"),
                payload.get("salary_range"),
                "to",
            ),
            currency=_extract_salary_currency(
                payload.get("salary"),
                payload.get("salary_range"),
            ),
            employment_type=_extract_primary_employment_type(payload),
            published_at=_to_text(payload.get("published_at")) or seed.published_at,
            description=_html_to_text(payload.get("description")),
            skills=_extract_key_skills(payload.get("key_skills")),
            apply_url=_to_text(payload.get("response_url"))
            or _to_text(payload.get("apply_alternate_url")),
            raw_meta={
                "alternate_url": _to_text(payload.get("alternate_url"))
                or seed.raw_meta.get("alternate_url"),
                "public_company_url": _to_text(employer.get("alternate_url"))
                or seed.raw_meta.get("public_company_url"),
                "languages": _extract_languages(payload.get("languages")),
                "professional_roles": _extract_named_values(payload.get("professional_roles")),
                "schedule": _extract_named_value(payload.get("schedule")),
                "employment": _extract_named_value(payload.get("employment")),
                "employment_form": _extract_named_value(payload.get("employment_form")),
                "work_format": _extract_named_values(payload.get("work_format")),
                "address": _extract_address(payload.get("address")),
            },
        )

    def parse_company_page(self, html_text: str, company_url: str) -> CompanyDetail | None:
        payload = _load_json_payload(html_text, stage="company")
        company_name = _to_text(payload.get("name"))
        about = _html_to_text(payload.get("description")) or _html_to_text(
            payload.get("branded_description")
        )

        contacts: list[str] = []
        site_url = _to_text(payload.get("site_url"))
        if site_url:
            contacts.append(site_url)

        contacts = list(dict.fromkeys(contact for contact in contacts if contact))
        if not company_name and not about and not contacts:
            return None

        return CompanyDetail(
            company_name=company_name,
            company_url=company_url,
            company_about=about,
            company_contacts=contacts,
            raw_meta={
                "alternate_url": _to_text(payload.get("alternate_url")),
                "logo_urls": (
                    payload.get("logo_urls") if isinstance(payload.get("logo_urls"), dict) else {}
                ),
                "open_vacancies": _to_int(payload.get("open_vacancies")),
            },
        )

    def _build_record(
        self,
        *,
        seed: VacancySeed,
        detail: VacancyDetail,
        company: CompanyDetail | None,
    ) -> VacancyRecord:
        record = super()._build_record(seed=seed, detail=detail, company=company)

        public_job_url = (
            detail.raw_meta.get("alternate_url")
            or seed.raw_meta.get("alternate_url")
            or record.job_url
        )
        public_company_url = (
            (company.raw_meta.get("alternate_url") if company is not None else None)
            or detail.raw_meta.get("public_company_url")
            or seed.raw_meta.get("public_company_url")
            or record.company_url
        )

        return record.model_copy(
            update={
                "job_url": self._canonical_job_url(public_job_url),
                "company_url": public_company_url,
            }
        )

    def build_fallback_record(self, seed: VacancySeed) -> VacancyRecord | None:
        snippet = seed.raw_meta.get("snippet")
        snippet_parts: list[str] = []
        if isinstance(snippet, dict):
            requirement = _to_text(snippet.get("requirement"))
            responsibility = _to_text(snippet.get("responsibility"))
            if requirement:
                snippet_parts.append(f"Requirements: {requirement}")
            if responsibility:
                snippet_parts.append(f"Responsibilities: {responsibility}")

        detail = VacancyDetail(
            title=seed.title,
            company_name=seed.company_name,
            company_url=seed.company_url,
            location=seed.location,
            salary_text=seed.salary_text,
            published_at=seed.published_at,
            description="\n".join(snippet_parts) or None,
            apply_url=_to_text(seed.raw_meta.get("apply_alternate_url")),
            raw_meta={
                "alternate_url": _to_text(seed.raw_meta.get("alternate_url")),
                "public_company_url": _to_text(seed.raw_meta.get("public_company_url")),
                "schedule": _to_text(seed.raw_meta.get("schedule")),
                "employment": _to_text(seed.raw_meta.get("employment")),
                "employment_form": _to_text(seed.raw_meta.get("employment_form")),
                "work_format": seed.raw_meta.get("work_format"),
                "detail_fallback_used": True,
            },
        )
        return self._build_record(seed=seed, detail=detail, company=None)

    def _build_search_params(
        self,
        query_term: str,
        area_ids: tuple[str, ...],
        intent: SearchIntent,
        *,
        page: int,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "host": HH_HOST,
            "page": page,
            "per_page": 100,
            "text": query_term,
        }
        if area_ids:
            params["area"] = list(area_ids)
        if intent.remote_only:
            params["work_format"] = "REMOTE"
        if intent.salary_from is not None:
            params["salary"] = intent.salary_from
        return params

    async def _resolve_area_ids(
        self,
        client: httpx.AsyncClient,
        locations: list[str],
    ) -> tuple[tuple[str, ...], list[ScrapeError]]:
        if not locations:
            return (), []

        errors: list[ScrapeError] = []
        semaphore = asyncio.Semaphore(4)

        async def resolve_location(raw_location: str) -> str | None:
            location = raw_location.strip()
            if not location:
                return None
            if location.isdigit():
                return location

            params = {"text": location, "host": HH_HOST}
            async with semaphore:
                try:
                    response = await client.get(
                        AREA_SUGGEST_URL,
                        params=params,
                        headers=self.build_request_headers("area_suggest"),
                    )
                    response.raise_for_status()
                except Exception as exc:
                    errors.append(
                        ScrapeError(
                            stage="query_plan",
                            url=f"{AREA_SUGGEST_URL}?{urlencode(params)}",
                            message=f"area_resolution_failed:{location}: {exc}",
                        )
                    )
                    return None

            payload = response.json()
            items = payload.get("items", []) if isinstance(payload, dict) else []
            area_id = _pick_area_id(items, location)
            if area_id is None:
                errors.append(
                    ScrapeError(
                        stage="query_plan",
                        url=f"{AREA_SUGGEST_URL}?{urlencode(params)}",
                        message=f"area_resolution_failed:{location}",
                    )
                )
            return area_id

        resolved = await asyncio.gather(*(resolve_location(location) for location in locations))
        if errors:
            return (), errors

        area_ids = tuple(dict.fromkeys(area_id for area_id in resolved if area_id))
        return area_ids, []


def _load_json_payload(raw_text: str, *, stage: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"hh_{stage}_is_not_json") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"hh_{stage}_payload_is_not_object")
    return payload


def _to_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = " ".join(value.split())
        return cleaned or None
    cleaned = " ".join(str(value).split())
    return cleaned or None


def _to_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _extract_named_value(value: Any) -> str | None:
    if isinstance(value, dict):
        return _to_text(value.get("name"))
    return None


def _extract_named_values(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    values: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = _to_text(item.get("name"))
        if name:
            values.append(name)
    return list(dict.fromkeys(values))


def _extract_location(payload: dict[str, Any]) -> str | None:
    address = _extract_address(payload.get("address"))
    area = payload.get("area") if isinstance(payload.get("area"), dict) else {}
    area_name = _to_text(area.get("name"))
    if address and area_name and address != area_name:
        return f"{area_name}, {address}"
    return address or area_name


def _extract_address(value: Any) -> str | None:
    if isinstance(value, dict):
        return _to_text(value.get("raw"))
    return None


def _format_salary_text(salary: Any, salary_range: Any) -> str | None:
    payload = (
        salary
        if isinstance(salary, dict)
        else salary_range
        if isinstance(salary_range, dict)
        else None
    )
    if payload is None:
        return None

    salary_from = _to_int(payload.get("from"))
    salary_to = _to_int(payload.get("to"))
    currency = _to_text(payload.get("currency"))
    parts: list[str] = []
    if salary_from is not None and salary_to is not None:
        parts.append(f"{salary_from} - {salary_to}")
    elif salary_from is not None:
        parts.append(f"from {salary_from}")
    elif salary_to is not None:
        parts.append(f"up to {salary_to}")

    if currency:
        parts.append(currency)

    mode = payload.get("mode") if isinstance(payload.get("mode"), dict) else {}
    mode_name = _to_text(mode.get("name"))
    if mode_name:
        parts.append(mode_name)

    return " ".join(parts) or None


def _extract_salary_bound(salary: Any, salary_range: Any, field: str) -> int | None:
    payload = (
        salary
        if isinstance(salary, dict)
        else salary_range
        if isinstance(salary_range, dict)
        else None
    )
    if payload is None:
        return None
    return _to_int(payload.get(field))


def _extract_salary_currency(salary: Any, salary_range: Any) -> str | None:
    payload = (
        salary
        if isinstance(salary, dict)
        else salary_range
        if isinstance(salary_range, dict)
        else None
    )
    if payload is None:
        return None
    return _to_text(payload.get("currency"))


def _extract_primary_employment_type(payload: dict[str, Any]) -> str | None:
    for value in (
        payload.get("employment_form"),
        payload.get("employment"),
        payload.get("schedule"),
    ):
        named_value = _extract_named_value(value)
        if named_value:
            return named_value
    return None


def _extract_key_skills(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    result: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        skill_name = _to_text(item.get("name"))
        if skill_name:
            result.append(skill_name)
    return list(dict.fromkeys(result))


def _extract_languages(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    result: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        language = item.get("language") if isinstance(item.get("language"), dict) else {}
        language_name = _to_text(language.get("name"))
        level = item.get("level") if isinstance(item.get("level"), dict) else {}
        level_name = _to_text(level.get("name"))
        if language_name and level_name:
            result.append(f"{language_name}: {level_name}")
        elif language_name:
            result.append(language_name)
    return list(dict.fromkeys(result))


def _html_to_text(value: Any) -> str | None:
    raw_html = _to_text(value)
    if not raw_html:
        return None

    try:
        fragment = html.fromstring(f"<div>{raw_html}</div>")
    except Exception:
        return raw_html

    for node in fragment.xpath("//script|//style"):
        parent = node.getparent()
        if parent is not None:
            parent.remove(node)

    text = " ".join(fragment.xpath("//text()"))
    cleaned = " ".join(text.split())
    return cleaned or None


def _query_param(url: str, name: str) -> str | None:
    values = parse_qs(urlsplit(url).query).get(name)
    if not values:
        return None
    return values[-1]


def _replace_query_param(url: str, name: str, value: str) -> str:
    parts = urlsplit(url)
    params = parse_qs(parts.query)
    params[name] = [value]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params, doseq=True), ""))


def _pick_area_id(items: Any, location: str) -> str | None:
    if not isinstance(items, list):
        return None

    normalized_location = location.casefold().strip()
    first_item_id: str | None = None
    for item in items:
        if not isinstance(item, dict):
            continue
        area_id = _to_text(item.get("id"))
        area_text = _to_text(item.get("text"))
        if area_id and first_item_id is None:
            first_item_id = area_id
        if area_id and area_text and area_text.casefold() == normalized_location:
            return area_id
    return first_item_id
