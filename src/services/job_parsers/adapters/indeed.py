from __future__ import annotations

import asyncio
import json
import re
from typing import Any
from urllib.parse import parse_qs, urldefrag, urlencode, urljoin, urlsplit, urlunsplit

import httpx
from lxml import html
from scrapling.fetchers import FetcherSession

from src.logger import get_logger
from src.services.job_parsers.base import BaseJobParser
from src.services.job_parsers.registry import register_parser
from src.services.job_parsers.schemas import (
    CompanyDetail,
    ListingPageResult,
    ScrapeError,
    ScrapeRunResult,
    SearchIntent,
    VacancyDetail,
    VacancySeed,
)

BASE_URL = "https://www.indeed.com"

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_CHALLENGE_MARKERS = (
    "just a moment",
    "turnstile",
    "cdn-cgi/challenge-platform",
    "cf_chl",
    "cloudflare",
)

logger = get_logger("services.job_parsers.indeed")
_INDEED_SESSION_PROFILES = (["chrome"], ["safari"])
_SUSPICIOUS_TITLES = (
    "security check - indeed.com",
    "additional verification required",
    "access denied",
)


@register_parser("indeed")
class IndeedParser(BaseJobParser):
    def __init__(self) -> None:
        self._session_lock = asyncio.Lock()
        self._fetcher_session: FetcherSession | None = None
        self._active_profile: list[str] | None = None

    def site_code(self) -> str:
        return "indeed"

    def supports_native_query_search(self) -> bool:
        return True

    def build_request_headers(self, stage: str) -> dict[str, str]:
        return _BROWSER_HEADERS

    async def scrape_by_intent(
        self,
        intent: SearchIntent,
        *,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 20.0,
        max_pages_safety: int = 100,
    ) -> ScrapeRunResult:
        try:
            return await super().scrape_by_intent(
                intent,
                client=client,
                timeout_seconds=timeout_seconds,
                max_pages_safety=max_pages_safety,
            )
        finally:
            async with self._session_lock:
                await self._reset_fetcher_session()

    def build_search_urls(self, intent: SearchIntent) -> list[str]:
        locations = intent.locations[:]
        if intent.remote_only and "remote" not in [value.lower() for value in locations]:
            locations.append("remote")
        if not locations:
            locations = [""]

        urls: list[str] = []
        for term in self.build_query_terms(intent):
            for location in locations:
                params = {
                    "q": term,
                    "sort": "date",
                }
                if location:
                    params["l"] = location
                urls.append(f"{BASE_URL}/jobs?{urlencode(params)}")
        return sorted(set(urls))

    def _canonical_job_url(self, url: str) -> str:
        url_no_fragment, _ = urldefrag(url.strip())
        parts = urlsplit(url_no_fragment)
        jk = parse_qs(parts.query).get("jk", [None])[0]
        if jk:
            return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode({"jk": jk}), ""))
        return super()._canonical_job_url(url)

    async def fetch_page_text(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        stage: str,
        errors: list[ScrapeError],
    ) -> str | None:
        del client

        async with self._session_lock:
            try:
                if stage == "listing":
                    result = await self._fetch_listing_text(url)
                else:
                    result = await self._fetch_non_listing_text(url, stage=stage)
            except Exception as exc:
                errors.append(ScrapeError(stage=stage, url=url, message=str(exc)))
                logger.error(
                    "scrapling_fetch_failed",
                    site=self.site_code(),
                    stage=stage,
                    url=url,
                    error=str(exc),
                )
                await self._reset_fetcher_session()
                return None

        if result["html_text"] is None:
            message = result["error"] or "scrapling_fetch_failed"
            errors.append(ScrapeError(stage=stage, url=url, message=message))
            logger.error(
                "scrapling_fetch_failed",
                site=self.site_code(),
                stage=stage,
                url=url,
                error=message,
                profile=result.get("profile"),
                transport="scrapling_fetcher_session",
            )
            return None

        return result["html_text"]

    def parse_listing_page(self, html_text: str, page_url: str) -> ListingPageResult:
        tree = html.fromstring(html_text)
        vacancies: list[VacancySeed] = []
        seen: set[str] = set()

        card_nodes = tree.xpath(
            '//*[starts-with(@id, "job_") or starts-with(@id, "sj_")] | '
            '//div[@data-testid="slider_item"]'
        )
        if not card_nodes:
            card_nodes = tree.xpath(
                "//li[.//button[contains(translate(normalize-space(.), "
                '"FULLDETAILSOF", "fulldetailsof"), "full details of")]]'
            )

        for card in card_nodes:
            jk = _extract_card_job_key(card)
            if not jk:
                continue

            job_url = f"{BASE_URL}/viewjob?jk={jk}"
            if job_url in seen:
                continue
            seen.add(job_url)

            company_name = _extract_best_text(
                card.xpath(
                    './/*[contains(@data-testid, "company-name")]/text() | '
                    './/*[contains(@class, "companyName")]/text() | '
                    './/*[contains(@class, "company_location")]/preceding-sibling::*[1]//text()'
                )
            )
            company_href = _first_text(card.xpath('.//a[contains(@href, "/cmp/")]/@href'))
            location = _extract_best_text(
                card.xpath(
                    './/*[contains(@data-testid, "text-location")]/text() | '
                    './/*[contains(@class, "companyLocation")]/text()'
                )
            )
            salary_text = _extract_best_text(
                card.xpath(
                    './/*[contains(@class, "salary-snippet")]/text() | '
                    './/*[contains(@class, "estimated-salary")]/text()'
                )
            )
            published = _extract_best_text(
                card.xpath('.//text()[contains(., "Posted") or contains(., "EmployerActive")]')
            )
            title = _extract_best_text(
                card.xpath(
                    './/a[contains(@class, "jcs-JobTitle")]//text() | '
                    ".//h2//a//text() | "
                    ".//h2//button//text()"
                )
            )

            vacancies.append(
                VacancySeed(
                    job_url=job_url,
                    title=title,
                    company_name=company_name,
                    company_url=_absolute_url(company_href) if company_href else None,
                    location=location,
                    salary_text=salary_text,
                    published_at=published,
                    raw_meta={"source": "listing_dom", "jk": jk},
                )
            )

        next_href = _first_text(
            tree.xpath(
                '//a[@aria-label="Next Page"]/@href | //a[contains(@aria-label, "Next")]/@href'
            )
        )
        next_page_url = _normalize_listing_url(next_href) if next_href else None

        return ListingPageResult(vacancies=vacancies, next_page_url=next_page_url)

    def parse_job_detail_page(
        self, html_text: str, job_url: str, seed: VacancySeed
    ) -> VacancyDetail:
        tree = html.fromstring(html_text)
        job_posting = _extract_job_posting_from_jsonld(html_text)

        if job_posting is not None:
            salary_min, salary_max, currency, salary_text = _extract_jsonld_salary(job_posting)
            company_name = _jsonld_company_name(job_posting) or seed.company_name
            company_url = (
                _extract_company_url_from_dom(tree)
                or _jsonld_company_url(job_posting)
                or seed.company_url
            )
            return VacancyDetail(
                title=_to_text(job_posting.get("title")) or seed.title,
                company_name=company_name,
                company_url=company_url,
                location=_extract_jsonld_location(job_posting) or seed.location,
                salary_text=salary_text or seed.salary_text,
                salary_min=salary_min,
                salary_max=salary_max,
                currency=currency,
                employment_type=_normalize_employment_type(job_posting.get("employmentType")),
                published_at=_to_text(job_posting.get("datePosted")) or seed.published_at,
                description=_to_html_text(job_posting.get("description")),
                apply_url=_extract_apply_url(tree),
                raw_meta={"source": "jsonld", "identifier": job_posting.get("identifier")},
            )

        title = _extract_best_text(tree.xpath("//h1//text()")) or seed.title
        company_name = (
            _extract_best_text(
                tree.xpath(
                    '//*[contains(@data-testid, "inlineHeader-companyName")]/text() | '
                    '//*[contains(@class, "jobsearch-InlineCompanyRating")]//text()'
                )
            )
            or seed.company_name
        )

        location = (
            _extract_best_text(
                tree.xpath(
                    '//*[contains(@data-testid, "job-location")]/text() | '
                    '//*[contains(@class, "jobsearch-JobInfoHeader-subtitle")]//text()'
                )
            )
            or seed.location
        )

        salary_text = (
            _extract_best_text(
                tree.xpath(
                    '//*[contains(@id, "salaryInfoAndJobType")]//text() | '
                    '//*[contains(@class, "salary-snippet-container")]//text()'
                )
            )
            or seed.salary_text
        )

        description = _clean_text(" ".join(tree.xpath('//div[@id="jobDescriptionText"]//text()')))
        if not description:
            description = _clean_text(" ".join(tree.xpath("//main//text()")))

        employment_type = _extract_employment_type_from_dom(tree)

        return VacancyDetail(
            title=title,
            company_name=company_name,
            company_url=_extract_company_url_from_dom(tree) or seed.company_url,
            location=location,
            salary_text=salary_text,
            employment_type=employment_type,
            published_at=seed.published_at,
            description=description or None,
            apply_url=_extract_apply_url(tree),
            raw_meta={"source": "dom"},
        )

    def parse_company_page(self, html_text: str, company_url: str) -> CompanyDetail | None:
        tree = html.fromstring(html_text)
        company_name = _normalize_company_name(_extract_best_text(tree.xpath("//h1//text()")))

        about = _extract_best_text(
            tree.xpath(
                '//*[contains(@data-testid, "about") or contains(@class, "cmp-About") or '
                'contains(@class, "css-1h7lukg")]//text()'
            )
        )
        if not about:
            about = _extract_best_text(tree.xpath('//meta[@name="description"]/@content'))

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
            if href.startswith("http") and "indeed.com" not in href:
                contacts.append(href)

        contacts = list(dict.fromkeys(contact for contact in contacts if contact))

        if not company_name and not about and not contacts:
            return None

        return CompanyDetail(
            company_name=company_name,
            company_url=company_url,
            company_about=about,
            company_contacts=contacts,
            raw_meta={"source": "company_dom"},
        )

    async def _fetch_listing_text(self, url: str) -> dict[str, Any]:
        last_result: dict[str, Any] | None = None
        for profile in _INDEED_SESSION_PROFILES:
            await self._ensure_fetcher_session(profile)
            result = await self._fetch_with_active_session(url, stage="listing")
            last_result = result
            if self._is_usable_listing_response(result["html_text"], result["status"]):
                self._active_profile = profile[:]
                return result

            logger.info(
                "scrapling_listing_retry",
                site=self.site_code(),
                stage="listing",
                url=url,
                profile=profile,
                status=result["status"],
                reason=result["reason"],
                transport="scrapling_fetcher_session",
            )
            await self._reset_fetcher_session()

        if last_result is None:
            return {
                "html_text": None,
                "status": None,
                "profile": None,
                "reason": "listing_fetch_failed",
                "error": "listing_fetch_failed",
            }

        return {
            **last_result,
            "html_text": None,
            "error": last_result["reason"],
        }

    async def _fetch_non_listing_text(self, url: str, *, stage: str) -> dict[str, Any]:
        profile = self._active_profile[:] if self._active_profile is not None else ["chrome"]
        await self._ensure_fetcher_session(profile)
        result = await self._fetch_with_active_session(url, stage=stage)

        if result["html_text"] is None:
            await self._reset_fetcher_session()
            return result

        if stage in {"detail", "company"} and (
            result["status"] is None
            or result["status"] >= 400
            or _looks_like_challenge(result["html_text"], stage=stage)
            or _has_suspicious_indeed_title(result["html_text"])
        ):
            message = f"{stage}_unusable_page"
            logger.info(
                "scrapling_unusable_page",
                site=self.site_code(),
                stage=stage,
                url=url,
                profile=profile,
                reason=message,
                transport="scrapling_fetcher_session",
            )
            return {
                **result,
                "html_text": None,
                "reason": message,
                "error": message,
            }

        return result

    async def _ensure_fetcher_session(self, profile: list[str]) -> None:
        if self._fetcher_session is not None and self._active_profile == profile:
            return

        await self._reset_fetcher_session()

        session_manager = FetcherSession(impersonate=profile)
        session = await asyncio.to_thread(session_manager.__enter__)
        self._fetcher_session = session
        self._active_profile = profile[:]

    async def _reset_fetcher_session(self) -> None:
        session = self._fetcher_session
        active_profile = self._active_profile
        self._fetcher_session = None
        self._active_profile = None
        if session is None:
            return

        try:
            await asyncio.to_thread(session.__exit__, None, None, None)
        except Exception as exc:
            logger.warning(
                "scrapling_session_close_failed",
                site=self.site_code(),
                profile=active_profile,
                error=str(exc),
            )

    async def _fetch_with_active_session(self, url: str, *, stage: str) -> dict[str, Any]:
        if self._fetcher_session is None:
            raise RuntimeError("fetcher_session_not_initialized")

        started = asyncio.get_running_loop().time()
        try:
            response = await asyncio.to_thread(
                self._fetcher_session.get,
                url,
                stealthy_headers=True,
                timeout=30_000,
            )
        except Exception as exc:
            return {
                "html_text": None,
                "status": None,
                "profile": self._active_profile[:] if self._active_profile else None,
                "reason": "session_get_failed",
                "error": str(exc),
            }

        html_text = response.html_content or response.body.decode("utf-8", errors="replace")
        status = getattr(response, "status", None)
        duration_seconds = round(asyncio.get_running_loop().time() - started, 3)
        reason = self._classify_fetch_result(html_text, status, stage=stage)
        logger.info(
            "scrapling_fetch_completed",
            site=self.site_code(),
            stage=stage,
            url=url,
            status=status,
            profile=self._active_profile,
            reason=reason,
            duration_seconds=duration_seconds,
            transport="scrapling_fetcher_session",
        )
        return {
            "html_text": html_text,
            "status": status,
            "profile": self._active_profile[:] if self._active_profile else None,
            "reason": reason,
            "error": None,
        }

    def _is_usable_listing_response(self, html_text: str | None, status: int | None) -> bool:
        if not html_text or status is None or status >= 400:
            return False
        if _looks_like_challenge(html_text, stage="listing"):
            return False
        if _has_suspicious_indeed_title(html_text):
            return False
        listing = self.parse_listing_page(html_text, "")
        return bool(listing.vacancies)

    def _classify_fetch_result(
        self,
        html_text: str | None,
        status: int | None,
        *,
        stage: str,
    ) -> str:
        if html_text is None:
            return "empty_html"
        if status is not None and status >= 400:
            return f"http_status_{status}"
        if _looks_like_challenge(html_text, stage=stage):
            return "challenge_detected"
        if stage == "listing":
            if _has_suspicious_indeed_title(html_text):
                return "suspicious_title"
            try:
                listing = self.parse_listing_page(html_text, "")
            except Exception:
                return "listing_parse_failed"
            if not listing.vacancies:
                return "listing_empty_after_fetch"
        return "ok"


def _looks_like_challenge(content: str, *, stage: str) -> bool:
    lowered = content.lower()
    if stage == "listing" and _has_listing_results(content):
        return False

    if "<title>just a moment..." in lowered:
        return True
    if "checking your browser before accessing" in lowered:
        return True
    if "security check - indeed.com" in lowered:
        return True
    if "additional verification required" in lowered:
        return True
    if "cf-challenge" in lowered:
        return True

    has_markers = any(marker in lowered for marker in _CHALLENGE_MARKERS)
    return has_markers and not _has_useful_indeed_content(content, stage=stage)


def _has_listing_results(content: str) -> bool:
    lowered = content.lower()
    return (
        "jcs-jobtitle" in lowered
        or 'aria-label="next page"' in lowered
        or "job post details" in lowered
    )


def _has_useful_indeed_content(content: str, *, stage: str) -> bool:
    lowered = content.lower()
    if stage == "listing":
        return _has_listing_results(content)
    if stage == "detail":
        return "jobdescriptiontext" in lowered or "job post details" in lowered
    if stage == "company":
        return (
            "careers and employment" in lowered
            or "about the company" in lowered
            or ('"/cmp/' in lowered and "snapshot" in lowered)
        )
    return _has_listing_results(content) or "job post details" in lowered


def _has_suspicious_indeed_title(content: str) -> bool:
    lowered = content.lower()
    match = re.search(r"<title>(.*?)</title>", lowered, flags=re.DOTALL)
    if match is None:
        return False
    title = _clean_text(match.group(1))
    return any(marker in title for marker in _SUSPICIOUS_TITLES)


def _normalize_company_name(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    if not cleaned:
        return None

    patterns = [
        r"\s+careers and employment\s*$",
        r"\s*\|\s*indeed\.com\s*$",
        r"\s*-\s*indeed\.com\s*$",
    ]
    previous = None
    while cleaned != previous:
        previous = cleaned
        for pattern in patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    normalized = _clean_text(cleaned)
    return normalized or None


def _normalize_listing_url(url: str | None) -> str | None:
    absolute = _absolute_url(url)
    if not absolute:
        return None

    parts = urlsplit(absolute)
    query = parse_qs(parts.query)
    normalized_query: dict[str, str] = {}
    for key in ("q", "l", "sort", "start"):
        value = query.get(key, [None])[0]
        if value:
            normalized_query[key] = value

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(normalized_query),
            "",
        )
    )


def _extract_job_posting_from_jsonld(html_text: str) -> dict[str, Any] | None:
    tree = html.fromstring(html_text)
    for raw in tree.xpath('//script[@type="application/ld+json"]/text()'):
        script_text = (raw or "").strip()
        if not script_text:
            continue
        try:
            payload = json.loads(script_text)
        except Exception:
            continue
        for node in _flatten_jsonld(payload):
            if "JobPosting" in _jsonld_types(node):
                return node
    return None


def _flatten_jsonld(payload: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        result.append(payload)
        graph = payload.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                result.extend(_flatten_jsonld(item))
    elif isinstance(payload, list):
        for item in payload:
            result.extend(_flatten_jsonld(item))
    return result


def _jsonld_types(payload: dict[str, Any]) -> set[str]:
    raw_type = payload.get("@type")
    if isinstance(raw_type, str):
        return {raw_type}
    if isinstance(raw_type, list):
        return {value for value in raw_type if isinstance(value, str)}
    return set()


def _extract_jsonld_salary(
    job_posting: dict[str, Any],
) -> tuple[int | None, int | None, str | None, str | None]:
    base_salary = job_posting.get("baseSalary")
    if not isinstance(base_salary, dict):
        return None, None, None, None

    currency = _to_text(base_salary.get("currency"))
    salary_value = base_salary.get("value")
    if isinstance(salary_value, dict):
        minimum = _to_int(salary_value.get("minValue") or salary_value.get("value"))
        maximum = _to_int(salary_value.get("maxValue") or salary_value.get("value"))
    else:
        minimum = _to_int(salary_value)
        maximum = minimum

    if minimum is None and maximum is None:
        return None, None, currency, None
    return minimum, maximum, currency, _format_salary_text(minimum, maximum, currency)


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


def _extract_jsonld_location(job_posting: dict[str, Any]) -> str | None:
    location = job_posting.get("jobLocation")
    if isinstance(location, dict):
        location = [location]
    if not isinstance(location, list):
        return None

    values: list[str] = []
    for item in location:
        if not isinstance(item, dict):
            continue
        address = item.get("address")
        if isinstance(address, dict):
            parts = [
                _to_text(address.get("streetAddress")),
                _to_text(address.get("addressLocality")),
                _to_text(address.get("addressRegion")),
                _to_text(address.get("postalCode")),
            ]
            joined = ", ".join(part for part in parts if part)
            if joined:
                values.append(joined)

    return " | ".join(dict.fromkeys(values)) if values else None


def _normalize_employment_type(raw_value: Any) -> str | None:
    if isinstance(raw_value, str):
        return _clean_text(raw_value)
    if isinstance(raw_value, list):
        values = [_clean_text(value) for value in raw_value if isinstance(value, str)]
        values = [value for value in values if value]
        return " | ".join(values) if values else None
    return None


def _extract_company_url_from_dom(tree: html.HtmlElement) -> str | None:
    href = _first_text(tree.xpath('//a[contains(@href, "/cmp/")]/@href'))
    return _absolute_url(href) if href else None


def _extract_apply_url(tree: html.HtmlElement) -> str | None:
    href = _first_text(
        tree.xpath(
            '//a[contains(translate(normalize-space(.), "APPLY", "apply"), "apply")]/@href | '
            '//button[contains(translate(normalize-space(.), "APPLY", "apply"), "apply")]/@href'
        )
    )
    return _absolute_url(href) if href else None


def _extract_employment_type_from_dom(tree: html.HtmlElement) -> str | None:
    candidates = [
        _clean_text(text)
        for text in tree.xpath('//*[contains(@id, "salaryInfoAndJobType")]//text()')
    ]
    for candidate in candidates:
        lowered = candidate.lower()
        if "full-time" in lowered or "part-time" in lowered or "contract" in lowered:
            return candidate
    return None


def _get_card_container(anchor: html.HtmlElement) -> html.HtmlElement:
    card_nodes = anchor.xpath('ancestor::*[starts-with(@id, "job_") or starts-with(@id, "sj_")][1]')
    if card_nodes:
        return card_nodes[0]
    parent_nodes = anchor.xpath("ancestor::*[1]")
    return parent_nodes[0] if parent_nodes else anchor


def _extract_jk(url: str) -> str | None:
    parsed = urlsplit(url)
    query_value = parse_qs(parsed.query).get("jk", [None])[0]
    if query_value:
        return query_value
    fromjk_value = parse_qs(parsed.query).get("fromjk", [None])[0]
    if fromjk_value:
        return fromjk_value
    match = re.search(r"(?:[?&]|^)(?:jk|fromjk)=([a-zA-Z0-9]{8,32})", url)
    if match:
        return match.group(1)
    return None


def _extract_card_job_key(card: html.HtmlElement) -> str | None:
    for value in card.xpath(".//@data-jk"):
        if isinstance(value, str):
            normalized = _clean_text(value)
            if re.fullmatch(r"[A-Za-z0-9]{8,32}", normalized):
                return normalized

    href_candidates = card.xpath(
        './/a[contains(@class, "jcs-JobTitle")]/@href | '
        ".//h2//a/@href | "
        './/a[contains(@href, "/viewjob")]/@href | '
        './/a[contains(@href, "fromjk=")]/@href'
    )
    for href in href_candidates:
        if not isinstance(href, str):
            continue
        jk = _extract_jk(href)
        if jk:
            return jk

    card_id = _to_text(card.get("id"))
    if card_id:
        match = re.search(r"(?:job|sj)_([A-Za-z0-9]{8,32})", card_id)
        if match:
            return match.group(1)

    return None


def _absolute_url(value: str | None) -> str | None:
    if not value:
        return None
    return urljoin(BASE_URL, value)


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
        if cleaned:
            return cleaned
    return None


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


def _to_html_text(value: Any) -> str | None:
    text = _to_text(value)
    if not text:
        return None
    try:
        return _clean_text(html.fromstring(text).text_content())
    except Exception:
        return text


def _clean_text(value: str | None) -> str:
    return " ".join((value or "").split())


def _format_salary_text(
    minimum: int | None, maximum: int | None, currency: str | None
) -> str | None:
    if minimum is None and maximum is None:
        return None
    if minimum is not None and maximum is not None and minimum != maximum:
        amount = f"{minimum:,} - {maximum:,}"
    else:
        amount = f"{(minimum or maximum or 0):,}"
    suffix = f" {currency}" if currency else ""
    return f"{amount}{suffix}".strip()
