import asyncio
from types import SimpleNamespace

from langgraph.errors import GraphRecursionError
from src.extensions.langchain import search_job as search_job_module
from src.workflows.search_job.schemas import SiteJobDetail, SiteJobListing


class FakeToolService:
    def __init__(self) -> None:
        self.list_calls: list[tuple[str, tuple[str, ...], bool, int | None, int, int]] = []
        self.detail_calls: list[list[str]] = []

    def get_site_profile(self):
        return SimpleNamespace(
            site="computrabajo",
            label="Computrabajo Mexico",
            supports_native_query_search=True,
            allowed_countries=["MX"],
            notes="Current implementation is bound to mx.computrabajo.com.",
            model_dump=lambda mode="json": {
                "site": "computrabajo",
                "label": "Computrabajo Mexico",
                "supports_native_query_search": True,
                "allowed_countries": ["MX"],
                "notes": "Current implementation is bound to mx.computrabajo.com.",
            },
        )

    async def list_site_jobs(self, *, args):
        signature = (
            args.search_text,
            tuple(args.locations),
            args.remote_only,
            args.salary_from,
            args.max_pages,
            args.max_items,
        )
        self.list_calls.append(signature)
        return [
            SiteJobListing(
                site="computrabajo",
                title=f"{args.search_text} role",
                company_name="Acme",
                location="Mexico",
                job_url=f"https://mx.computrabajo.com/job-{len(self.list_calls)}",
            )
        ]

    async def get_job_details(self, *, job_urls):
        self.detail_calls.append(list(job_urls))
        return [
            SiteJobDetail(
                site="computrabajo",
                job_url=job_url,
                title="ML Engineer",
                company_name="Acme",
                location="Mexico",
                description="Detailed role",
            )
            for job_url in job_urls
        ]


class FakeLoopingAgent:
    def __init__(self, tools):
        self.tools = {tool.name: tool for tool in tools}

    async def ainvoke(self, payload, config):
        _ = payload
        _ = config
        await self.tools["get_site_profile"].ainvoke({})
        await self.tools["list_site_jobs"].ainvoke(
            {
                "search_text": "ml engineer",
                "locations": ["Mexico"],
                "max_items": 50,
            }
        )
        await self.tools["list_site_jobs"].ainvoke(
            {
                "search_text": "ml engineer",
                "locations": ["Mexico"],
                "max_items": 50,
            }
        )
        await self.tools["list_site_jobs"].ainvoke(
            {
                "search_text": "senior ml engineer",
                "locations": ["Mexico"],
                "max_items": 50,
            }
        )
        await self.tools["list_site_jobs"].ainvoke(
            {
                "search_text": "lead ml engineer",
                "locations": ["Mexico"],
                "max_items": 50,
            }
        )
        await self.tools["get_job_details"].ainvoke(
            {
                "job_urls": [f"https://mx.computrabajo.com/job-{index}" for index in range(1, 12)]
            }
        )
        raise GraphRecursionError("loop")


class FakeTimeoutAgent:
    def __init__(self, tools):
        self.tools = {tool.name: tool for tool in tools}

    async def ainvoke(self, payload, config):
        _ = payload
        _ = config
        await self.tools["get_site_profile"].ainvoke({})
        await self.tools["list_site_jobs"].ainvoke(
            {
                "search_text": "ml engineer",
                "locations": ["Mexico"],
                "max_items": 50,
            }
        )
        await self.tools["get_job_details"].ainvoke(
            {
                "job_urls": [f"https://mx.computrabajo.com/job-{index}" for index in range(1, 4)]
            }
        )
        raise TimeoutError("agent timed out")


def test_run_site_agent_returns_partial_result_on_graph_recursion(monkeypatch) -> None:
    tool_service = FakeToolService()
    monkeypatch.setattr(search_job_module, "get_job_site_tools_service", lambda _: tool_service)
    monkeypatch.setattr(
        search_job_module,
        "create_agent",
        lambda **kwargs: FakeLoopingAgent(kwargs["tools"]),
    )

    service = search_job_module.LangChainSearchJobService(
        api_key="test-key",
        model="gemini-test",
        max_iterations=15,
    )

    result = asyncio.run(
        service.run_site_agent(
            site_name="computrabajo",
            search_strategy_summary="Focus on ML roles.",
            hard_preferences=["Mexico"],
            soft_preferences=[],
        )
    )

    assert result.status == "ok"
    assert result.reason == "partial_result_due_to_recursion_guard"
    assert len(result.selected_jobs) == 8
    assert result.queries_used == ["ml engineer", "senior ml engineer", "lead ml engineer"]
    assert len(tool_service.list_calls) == 3
    assert len(tool_service.detail_calls) == 1
    assert len(tool_service.detail_calls[0]) == 8


def test_run_site_agent_returns_partial_result_on_timeout(monkeypatch) -> None:
    tool_service = FakeToolService()
    monkeypatch.setattr(search_job_module, "get_job_site_tools_service", lambda _: tool_service)
    monkeypatch.setattr(
        search_job_module,
        "create_agent",
        lambda **kwargs: FakeTimeoutAgent(kwargs["tools"]),
    )

    service = search_job_module.LangChainSearchJobService(
        api_key="test-key",
        model="gemini-test",
        max_iterations=15,
    )

    result = asyncio.run(
        service.run_site_agent(
            site_name="computrabajo",
            search_strategy_summary="Focus on ML roles.",
            hard_preferences=["Mexico"],
            soft_preferences=[],
        )
    )

    assert result.status == "ok"
    assert result.reason == "partial_result_due_to_agent_timeout"
    assert len(result.selected_jobs) == 3
    assert result.queries_used == ["ml engineer"]
