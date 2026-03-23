from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from functools import lru_cache

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.errors import GraphRecursionError
from pydantic import ValidationError

from src.config import get_settings
from src.extensions.gemini import GeminiIntegrationError
from src.logger import get_logger
from src.services.job_search_tools import get_job_site_tools_service
from src.services.job_search_tools.service import ListSiteJobsArgs
from src.workflows.search_job.schemas import SiteAgentResult, SiteJobDetail, SiteJobListing

logger = get_logger("integrations.langchain.search_job")

LISTING_CALL_BUDGET = 3
DETAIL_CALL_BUDGET = 1
DETAIL_URL_CLAMP = 8


class LangChainSearchJobError(RuntimeError):
    """Raised when a site-agent job search request fails."""


@dataclass
class SiteAgentRuntimeState:
    """Mutable runtime guardrails and accumulators for one site-agent run."""

    queries_used_accumulator: list[str] = field(default_factory=list)
    listings_seen_accumulator: dict[str, SiteJobListing] = field(default_factory=dict)
    selected_jobs_accumulator: dict[str, SiteJobDetail] = field(default_factory=dict)
    list_call_signatures_seen: dict[tuple[object, ...], list[SiteJobListing]] = field(
        default_factory=dict
    )
    detail_call_signatures_seen: dict[tuple[str, ...], list[SiteJobDetail]] = field(
        default_factory=dict
    )
    notes: list[str] = field(default_factory=list)

    def to_partial_result(self, *, site_name: str, reason: str) -> SiteAgentResult:
        selected_jobs = list(self.selected_jobs_accumulator.values())
        listings_seen = list(self.listings_seen_accumulator.values())
        status = "ok" if selected_jobs else "failed"
        notes = list(self.notes)
        if reason not in notes:
            notes.append(reason)
        return SiteAgentResult(
            site=site_name,
            status=status,
            reason=reason,
            queries_used=list(self.queries_used_accumulator),
            listings_seen=listings_seen,
            selected_jobs=selected_jobs,
            notes=notes,
        )


class LangChainSearchJobService:
    """Per-site ReAct search agents over the site-tools contract."""

    def __init__(self, *, api_key: str, model: str, max_iterations: int) -> None:
        settings = get_settings()
        self.model_name = model
        self.max_iterations = max_iterations
        self.max_retries = settings.gemini_max_retries
        self.agent_timeout_seconds = float(settings.search_job_site_agent_timeout_seconds)
        self._model = ChatGoogleGenerativeAI(
            model=model,
            api_key=api_key,
            temperature=0.1,
            request_timeout=float(settings.gemini_request_timeout_seconds),
        )

    async def run_site_agent(
        self,
        *,
        site_name: str,
        search_strategy_summary: str,
        hard_preferences: list[str],
        soft_preferences: list[str],
    ) -> SiteAgentResult:
        """Run one site-constrained search agent and return a structured result."""
        settings = get_settings()
        log = logger.bind(
            site=site_name,
            model=self.model_name,
        )
        stage_state: dict[str, object] = {
            "current_stage": "load_site_profile",
            "last_completed_stage": None,
            "tool_call_count": 0,
        }
        runtime_state = SiteAgentRuntimeState()

        tool_service = get_job_site_tools_service(site_name)
        site_profile = tool_service.get_site_profile()
        if not site_profile.supports_native_query_search:
            log.info(
                "search_job_site_agent_skipped",
                reason="native_query_search_not_supported",
                current_stage=stage_state["current_stage"],
            )
            return SiteAgentResult(
                site=site_name,
                status="skipped",
                reason="native_query_search_not_supported",
                notes=[site_profile.notes] if site_profile.notes else [],
            )

        @tool("get_site_profile")
        def get_site_profile_tool() -> dict[str, object]:
            """Return static capability metadata about the assigned job site."""
            stage_state["tool_call_count"] = int(stage_state["tool_call_count"]) + 1
            stage_state["current_stage"] = "tool:get_site_profile"
            log.info(
                "search_job_site_tool_started",
                tool_name="get_site_profile",
                tool_call_count=stage_state["tool_call_count"],
            )
            started_at = time.monotonic()
            result = site_profile.model_dump(mode="json")
            stage_state["last_completed_stage"] = "tool:get_site_profile"
            log.info(
                "search_job_site_tool_completed",
                tool_name="get_site_profile",
                tool_call_count=stage_state["tool_call_count"],
                duration_ms=round((time.monotonic() - started_at) * 1000, 2),
            )
            return result

        @tool("list_site_jobs")
        async def list_site_jobs_tool(
            search_text: str,
            locations: list[str] | None = None,
            remote_only: bool = False,
            salary_from: int | None = None,
            max_pages: int = 1,
            max_items: int = 10,
        ) -> list[dict[str, object]]:
            """Search listing pages on the assigned site and return compact job listings."""
            stage_state["tool_call_count"] = int(stage_state["tool_call_count"]) + 1
            stage_state["current_stage"] = "tool:list_site_jobs"
            normalized_locations = tuple(locations or [])
            clamped_max_pages = max(1, min(max_pages, settings.search_job_listing_max_pages))
            clamped_max_items = max(1, min(max_items, settings.search_job_listing_max_items))
            signature = (
                search_text.strip(),
                normalized_locations,
                remote_only,
                salary_from,
                clamped_max_pages,
                clamped_max_items,
            )

            if signature in runtime_state.list_call_signatures_seen:
                cached_results = runtime_state.list_call_signatures_seen[signature]
                log.info(
                    "search_job_site_tool_completed",
                    tool_name="list_site_jobs",
                    tool_call_count=stage_state["tool_call_count"],
                    duration_ms=0.0,
                    listings_count=len(cached_results),
                    partial_fallback_used=True,
                    cached_result_used=True,
                )
                return [result.model_dump(mode="json") for result in cached_results]

            if len(runtime_state.list_call_signatures_seen) >= LISTING_CALL_BUDGET:
                note = "listing_budget_exhausted_returning_cached_results"
                runtime_state.notes.append(note)
                cached_results = list(runtime_state.listings_seen_accumulator.values())[
                    : settings.search_job_listing_max_items
                ]
                log.info(
                    "search_job_site_tool_completed",
                    tool_name="list_site_jobs",
                    tool_call_count=stage_state["tool_call_count"],
                    duration_ms=0.0,
                    listings_count=len(cached_results),
                    partial_fallback_used=True,
                    listing_budget_exhausted=True,
                )
                return [result.model_dump(mode="json") for result in cached_results]

            log.info(
                "search_job_site_tool_started",
                tool_name="list_site_jobs",
                tool_call_count=stage_state["tool_call_count"],
                search_text=search_text,
                locations=list(normalized_locations),
                remote_only=remote_only,
                salary_from=salary_from,
                max_pages=clamped_max_pages,
                max_items=clamped_max_items,
            )
            started_at = time.monotonic()
            try:
                results = await tool_service.list_site_jobs(
                    args=ListSiteJobsArgs(
                        search_text=search_text,
                        locations=list(normalized_locations),
                        remote_only=remote_only,
                        salary_from=salary_from,
                        max_pages=clamped_max_pages,
                        max_items=clamped_max_items,
                    )
                )
            except Exception as exc:
                log.error(
                    "search_job_site_tool_failed",
                    tool_name="list_site_jobs",
                    tool_call_count=stage_state["tool_call_count"],
                    current_stage=stage_state["current_stage"],
                    error=str(exc),
                    exc_info=True,
                )
                raise

            if search_text not in runtime_state.queries_used_accumulator:
                runtime_state.queries_used_accumulator.append(search_text)
            for result in results:
                runtime_state.listings_seen_accumulator[result.job_url] = result
            runtime_state.list_call_signatures_seen[signature] = results
            stage_state["last_completed_stage"] = "tool:list_site_jobs"
            log.info(
                "search_job_site_tool_completed",
                tool_name="list_site_jobs",
                tool_call_count=stage_state["tool_call_count"],
                duration_ms=round((time.monotonic() - started_at) * 1000, 2),
                listings_count=len(results),
            )
            return [result.model_dump(mode="json") for result in results]

        @tool("get_job_details")
        async def get_job_details_tool(job_urls: list[str]) -> list[dict[str, object]]:
            """Fetch normalized detail payloads for shortlisted job URLs from this site."""
            stage_state["tool_call_count"] = int(stage_state["tool_call_count"]) + 1
            stage_state["current_stage"] = "tool:get_job_details"
            clamped_job_urls = tuple(dict.fromkeys(job_urls[:DETAIL_URL_CLAMP]))

            if clamped_job_urls in runtime_state.detail_call_signatures_seen:
                cached_results = runtime_state.detail_call_signatures_seen[clamped_job_urls]
                log.info(
                    "search_job_site_tool_completed",
                    tool_name="get_job_details",
                    tool_call_count=stage_state["tool_call_count"],
                    duration_ms=0.0,
                    details_count=len(cached_results),
                    partial_fallback_used=True,
                    cached_result_used=True,
                )
                return [result.model_dump(mode="json") for result in cached_results]

            if len(runtime_state.detail_call_signatures_seen) >= DETAIL_CALL_BUDGET:
                note = "detail_budget_exhausted_returning_cached_results"
                runtime_state.notes.append(note)
                cached_results = list(runtime_state.selected_jobs_accumulator.values())
                log.info(
                    "search_job_site_tool_completed",
                    tool_name="get_job_details",
                    tool_call_count=stage_state["tool_call_count"],
                    duration_ms=0.0,
                    details_count=len(cached_results),
                    partial_fallback_used=True,
                    detail_budget_exhausted=True,
                )
                return [result.model_dump(mode="json") for result in cached_results]

            log.info(
                "search_job_site_tool_started",
                tool_name="get_job_details",
                tool_call_count=stage_state["tool_call_count"],
                requested_job_urls_count=len(clamped_job_urls),
            )
            started_at = time.monotonic()
            try:
                results = await tool_service.get_job_details(job_urls=list(clamped_job_urls))
            except Exception as exc:
                log.error(
                    "search_job_site_tool_failed",
                    tool_name="get_job_details",
                    tool_call_count=stage_state["tool_call_count"],
                    current_stage=stage_state["current_stage"],
                    error=str(exc),
                    exc_info=True,
                )
                raise

            for result in results:
                runtime_state.selected_jobs_accumulator[result.job_url] = result
            runtime_state.detail_call_signatures_seen[clamped_job_urls] = results
            stage_state["last_completed_stage"] = "tool:get_job_details"
            log.info(
                "search_job_site_tool_completed",
                tool_name="get_job_details",
                tool_call_count=stage_state["tool_call_count"],
                duration_ms=round((time.monotonic() - started_at) * 1000, 2),
                details_count=len(results),
            )
            return [result.model_dump(mode="json") for result in results]

        agent = create_agent(
            model=self._model,
            tools=[get_site_profile_tool, list_site_jobs_tool, get_job_details_tool],
            response_format=SiteAgentResult,
            system_prompt=self._system_prompt(
                site_name=site_name,
                site_label=site_profile.label,
                allowed_countries=site_profile.allowed_countries,
                notes=site_profile.notes,
            ),
            name=f"{site_name}_site_agent",
        )
        log.info(
            "search_job_site_agent_invoke_started",
            current_stage="agent_invoke",
            recursion_limit=self.max_iterations,
        )
        stage_state["current_stage"] = "agent_invoke"
        started_at = time.monotonic()
        try:
            result = await self._ainvoke_with_retry(
                agent=agent,
                payload={
                    "messages": [
                        {
                            "role": "user",
                            "content": self._user_prompt(
                                site_name=site_name,
                                search_strategy_summary=search_strategy_summary,
                                hard_preferences=hard_preferences,
                                soft_preferences=soft_preferences,
                            ),
                        }
                    ]
                },
                recursion_limit=self.max_iterations,
                log=log,
                stage_state=stage_state,
            )
        except GraphRecursionError as exc:
            partial_result = runtime_state.to_partial_result(
                site_name=site_name,
                reason="partial_result_due_to_recursion_guard",
            )
            log.warning(
                "search_job_site_agent_recursion_guard_triggered",
                current_stage=stage_state["current_stage"],
                last_completed_stage=stage_state["last_completed_stage"],
                tool_call_count=stage_state["tool_call_count"],
                duration_ms=round((time.monotonic() - started_at) * 1000, 2),
                partial_fallback_used=True,
                selected_jobs_count=len(partial_result.selected_jobs),
                listings_seen_count=len(partial_result.listings_seen),
                error=str(exc),
            )
            if partial_result.selected_jobs or partial_result.listings_seen:
                return self._finalize_site_result(
                    site_name=site_name,
                    site_result=partial_result,
                )
            raise LangChainSearchJobError(f"Site agent failed for {site_name}.") from exc
        except TimeoutError as exc:
            partial_result = runtime_state.to_partial_result(
                site_name=site_name,
                reason="partial_result_due_to_agent_timeout",
            )
            log.warning(
                "search_job_site_agent_timeout_fallback",
                current_stage=stage_state["current_stage"],
                last_completed_stage=stage_state["last_completed_stage"],
                tool_call_count=stage_state["tool_call_count"],
                duration_ms=round((time.monotonic() - started_at) * 1000, 2),
                partial_fallback_used=True,
                selected_jobs_count=len(partial_result.selected_jobs),
                listings_seen_count=len(partial_result.listings_seen),
                error=str(exc),
            )
            if partial_result.selected_jobs or partial_result.listings_seen:
                return self._finalize_site_result(
                    site_name=site_name,
                    site_result=partial_result,
                )
            raise LangChainSearchJobError(f"Site agent timed out for {site_name}.") from exc
        except Exception as exc:
            log.error(
                "search_job_site_agent_invoke_failed",
                current_stage=stage_state["current_stage"],
                last_completed_stage=stage_state["last_completed_stage"],
                tool_call_count=stage_state["tool_call_count"],
                duration_ms=round((time.monotonic() - started_at) * 1000, 2),
                error_type=type(exc).__name__,
                error=str(exc),
                exc_info=True,
            )
            raise LangChainSearchJobError(f"Site agent failed for {site_name}.") from exc

        stage_state["current_stage"] = "validate_structured_response"
        log.info(
            "search_job_site_agent_invoke_completed",
            current_stage=stage_state["current_stage"],
            last_completed_stage=stage_state["last_completed_stage"],
            tool_call_count=stage_state["tool_call_count"],
            duration_ms=round((time.monotonic() - started_at) * 1000, 2),
        )

        structured_response = result.get("structured_response")
        if structured_response is None:
            partial_result = runtime_state.to_partial_result(
                site_name=site_name,
                reason="partial_result_due_to_missing_structured_response",
            )
            if partial_result.selected_jobs or partial_result.listings_seen:
                log.warning(
                    "search_job_site_agent_missing_structured_response_fallback",
                    current_stage=stage_state["current_stage"],
                    tool_call_count=stage_state["tool_call_count"],
                    partial_fallback_used=True,
                    selected_jobs_count=len(partial_result.selected_jobs),
                    listings_seen_count=len(partial_result.listings_seen),
                )
                return self._finalize_site_result(
                    site_name=site_name,
                    site_result=partial_result,
                )
            log.error(
                "search_job_site_agent_invalid_response",
                current_stage=stage_state["current_stage"],
                reason="missing_structured_response",
                tool_call_count=stage_state["tool_call_count"],
            )
            raise LangChainSearchJobError(
                f"Site agent did not return a structured response for {site_name}."
            )

        try:
            site_result = SiteAgentResult.model_validate(structured_response)
        except ValidationError as exc:
            partial_result = runtime_state.to_partial_result(
                site_name=site_name,
                reason="partial_result_due_to_invalid_structured_response",
            )
            if partial_result.selected_jobs or partial_result.listings_seen:
                log.warning(
                    "search_job_site_agent_invalid_response_fallback",
                    current_stage=stage_state["current_stage"],
                    tool_call_count=stage_state["tool_call_count"],
                    partial_fallback_used=True,
                    selected_jobs_count=len(partial_result.selected_jobs),
                    listings_seen_count=len(partial_result.listings_seen),
                    error=str(exc),
                )
                return self._finalize_site_result(
                    site_name=site_name,
                    site_result=partial_result,
                )
            log.error(
                "search_job_site_agent_invalid_response",
                current_stage=stage_state["current_stage"],
                reason="structured_response_validation_failed",
                tool_call_count=stage_state["tool_call_count"],
                error=str(exc),
                exc_info=True,
            )
            raise LangChainSearchJobError(
                f"Site agent returned an invalid payload for {site_name}."
            ) from exc

        merged_queries = list(
            dict.fromkeys(runtime_state.queries_used_accumulator + site_result.queries_used)
        )
        merged_listings = (
            site_result.listings_seen
            if site_result.listings_seen
            else list(runtime_state.listings_seen_accumulator.values())
        )
        merged_selected_jobs = (
            site_result.selected_jobs
            if site_result.selected_jobs
            else list(runtime_state.selected_jobs_accumulator.values())
        )
        runtime_state.notes.extend(
            note for note in site_result.notes if note not in runtime_state.notes
        )
        site_result = site_result.model_copy(
            update={
                "queries_used": merged_queries,
                "listings_seen": merged_listings,
                "selected_jobs": merged_selected_jobs,
                "notes": list(runtime_state.notes),
            }
        )
        return self._finalize_site_result(site_name=site_name, site_result=site_result)

    async def _ainvoke_with_retry(
        self,
        *,
        agent,
        payload: dict[str, object],
        recursion_limit: int,
        log,
        stage_state: dict[str, object],
    ):
        attempts = self.max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                return await asyncio.wait_for(
                    agent.ainvoke(payload, {"recursion_limit": recursion_limit}),
                    timeout=self.agent_timeout_seconds,
                )
            except Exception as exc:
                is_retryable = self._is_retryable_provider_error(exc)
                if not is_retryable or attempt >= attempts:
                    raise
                delay_seconds = min(8.0, (2 ** (attempt - 1)) + random.uniform(0.0, 0.5))
                log.warning(
                    "search_job_site_agent_retry_scheduled",
                    current_stage=stage_state["current_stage"],
                    last_completed_stage=stage_state["last_completed_stage"],
                    tool_call_count=stage_state["tool_call_count"],
                    retry_attempt=attempt,
                    provider_timeout_detected=True,
                    delay_seconds=round(delay_seconds, 2),
                    error=str(exc),
                )
                await asyncio.sleep(delay_seconds)

    @staticmethod
    def _finalize_site_result(*, site_name: str, site_result: SiteAgentResult) -> SiteAgentResult:
        settings = get_settings()
        if site_result.site != site_name:
            site_result = site_result.model_copy(update={"site": site_name})
        if len(site_result.listings_seen) > settings.search_job_listing_max_items:
            site_result = site_result.model_copy(
                update={
                    "listings_seen": site_result.listings_seen[
                        : settings.search_job_listing_max_items
                    ]
                }
            )
        if len(site_result.selected_jobs) > settings.search_job_site_max_selected_jobs:
            site_result = site_result.model_copy(
                update={
                    "selected_jobs": site_result.selected_jobs[
                        : settings.search_job_site_max_selected_jobs
                    ]
                }
            )

        logger.info(
            "search_job_site_agent_completed",
            site=site_name,
            status=site_result.status,
            selected_jobs_count=len(site_result.selected_jobs),
            partial_fallback_used=site_result.reason == "partial_result_due_to_recursion_guard",
        )
        return site_result

    @staticmethod
    def _is_retryable_provider_error(exc: Exception) -> bool:
        message = str(exc).upper()
        return any(
            marker in message
            for marker in (
                "504",
                "DEADLINE_EXCEEDED",
                "SERVICE UNAVAILABLE",
                "UNAVAILABLE",
                "INTERNAL",
                "TIMEOUT",
            )
        )

    @staticmethod
    def _system_prompt(
        *,
        site_name: str,
        site_label: str,
        allowed_countries: list[str],
        notes: str | None,
    ) -> str:
        countries_block = ", ".join(allowed_countries) if allowed_countries else "unknown"
        return (
            f"You are {site_label}, a job search agent assigned to exactly one source: "
            f"{site_name}. "
            f"This source is primarily relevant for countries/markets: {countries_block}. "
            f"Source notes: {notes or 'No additional notes.'} "
            "Always start by calling get_site_profile exactly once. "
            "Then use no more than three unique list_site_jobs calls with precise search strings. "
            "Never repeat an identical query or widen the search indefinitely. "
            "As soon as you have enough promising listings, call get_job_details once for the best "
            "URLs and then stop. "
            "If results are sparse, return the best partial shortlist rather than "
            "continuing to loop. "
            "Return a structured SiteAgentResult only. "
            "If the site is a poor fit for the user's constraints, or if the site does not support "
            "native search in this project, return status=skipped with a short reason. "
            "Do not invent job details. "
            "Prefer jobs that satisfy hard preferences first, then optimize for soft preferences. "
            "Keep notes concise and factual."
        )

    @staticmethod
    def _user_prompt(
        *,
        site_name: str,
        search_strategy_summary: str,
        hard_preferences: list[str],
        soft_preferences: list[str],
    ) -> str:
        hard_block = "\n".join(f"- {item}" for item in hard_preferences) or "- None"
        soft_block = "\n".join(f"- {item}" for item in soft_preferences) or "- None"
        return (
            f"Assigned site: {site_name}\n\n"
            "Start the search using the approved hiring strategy below.\n\n"
            f"Approved search strategy summary:\n{search_strategy_summary}\n\n"
            f"Hard preferences:\n{hard_block}\n\n"
            f"Soft preferences:\n{soft_block}\n\n"
            "Find the most relevant openings from this site only. "
            "Return the exact listings you inspected, the queries you used, and a shortlist of "
            "detailed jobs worth carrying into downstream unification."
        )


@lru_cache(maxsize=1)
def get_langchain_search_job_service() -> LangChainSearchJobService:
    """Build and cache the shared site-agent service."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise GeminiIntegrationError("Missing required Gemini setting: GEMINI_API_KEY")

    return LangChainSearchJobService(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        max_iterations=settings.search_job_site_agent_max_iterations,
    )
