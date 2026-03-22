from __future__ import annotations

import time
from functools import lru_cache

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import ValidationError

from src.config import get_settings
from src.extensions.gemini import GeminiIntegrationError
from src.logger import get_logger
from src.services.job_search_tools import get_job_site_tools_service
from src.services.job_search_tools.service import ListSiteJobsArgs
from src.workflows.search_job.schemas import SiteAgentResult

logger = get_logger("integrations.langchain.search_job")


class LangChainSearchJobError(RuntimeError):
    """Raised when a site-agent job search request fails."""


class LangChainSearchJobService:
    """Per-site ReAct search agents over the site-tools contract."""

    def __init__(self, *, api_key: str, model: str, max_iterations: int) -> None:
        self.model_name = model
        self.max_iterations = max_iterations
        self._model = ChatGoogleGenerativeAI(
            model=model,
            api_key=api_key,
            temperature=0.1,
            request_timeout=60.0,
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
        log = logger.bind(
            site=site_name,
            model=self.model_name,
        )
        stage_state: dict[str, object] = {
            "current_stage": "load_site_profile",
            "last_completed_stage": None,
            "tool_call_count": 0,
        }

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
            log.info(
                "search_job_site_tool_started",
                tool_name="list_site_jobs",
                tool_call_count=stage_state["tool_call_count"],
                search_text=search_text,
                locations=locations or [],
                remote_only=remote_only,
                salary_from=salary_from,
                max_pages=max_pages,
                max_items=max_items,
            )
            started_at = time.monotonic()
            try:
                results = await tool_service.list_site_jobs(
                    args=ListSiteJobsArgs(
                        search_text=search_text,
                        locations=locations or [],
                        remote_only=remote_only,
                        salary_from=salary_from,
                        max_pages=max_pages,
                        max_items=max_items,
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
            log.info(
                "search_job_site_tool_started",
                tool_name="get_job_details",
                tool_call_count=stage_state["tool_call_count"],
                requested_job_urls_count=len(job_urls),
            )
            started_at = time.monotonic()
            try:
                results = await tool_service.get_job_details(job_urls=job_urls)
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
            result = await agent.ainvoke(
                {
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
                {"recursion_limit": self.max_iterations},
            )
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

        stage_state["current_stage"] = "completed"
        if site_result.site != site_name:
            site_result = site_result.model_copy(update={"site": site_name})
        if len(site_result.selected_jobs) > get_settings().search_job_site_max_selected_jobs:
            site_result = site_result.model_copy(
                update={
                    "selected_jobs": site_result.selected_jobs[
                        : get_settings().search_job_site_max_selected_jobs
                    ]
                }
            )

        logger.info(
            "search_job_site_agent_completed",
            site=site_name,
            status=site_result.status,
            selected_jobs_count=len(site_result.selected_jobs),
            tool_call_count=stage_state["tool_call_count"],
        )
        return site_result

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
            "Use tools to inspect the site, search listings, and fetch details for promising jobs. "
            "Always start by checking get_site_profile. "
            "Return a structured SiteAgentResult only. "
            "If the site is a poor fit for the user's constraints, or if the site does not support "
            "native search in this project, return status=skipped with a short reason. "
            "Use list_site_jobs sparingly and prefer precise search strings. "
            "Call get_job_details only for the most promising URLs. "
            "Return at most 15 selected jobs. "
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
