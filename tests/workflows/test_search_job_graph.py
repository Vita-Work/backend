import asyncio

from src.workflows.search_job import nodes as search_job_nodes
from src.workflows.search_job.graph import build_search_job_graph
from src.workflows.search_job.schemas import SiteAgentResult, SiteJobDetail, UnifiedJob


class FakeSiteAgentService:
    async def run_site_agent(
        self,
        *,
        site_name: str,
        search_strategy_summary: str,
        hard_preferences: list[str],
        soft_preferences: list[str],
    ) -> SiteAgentResult:
        assert search_strategy_summary
        assert hard_preferences == ["remote"]
        assert soft_preferences == ["product"]
        if site_name == "beta":
            return SiteAgentResult(site="beta", status="skipped", reason="not_a_fit")
        return SiteAgentResult(
            site=site_name,
            status="ok",
            queries_used=["python backend remote"],
            selected_jobs=[
                SiteJobDetail(
                    site=site_name,
                    job_url=f"https://{site_name}.example/jobs/1",
                    title="Backend Engineer",
                    company_name=f"{site_name.title()} Corp",
                    location="Remote",
                    description="Backend role",
                    skills=["Python", "FastAPI"],
                )
            ],
        )


class FakeGeminiJobSearchService:
    async def unify_jobs_batch(
        self,
        *,
        search_strategy_summary: str,
        hard_preferences: list[str],
        soft_preferences: list[str],
        batch_jobs: list[dict[str, object]],
    ):
        assert search_strategy_summary
        return type(
            "BatchResult",
            (),
            {
                "jobs": [
                    UnifiedJob(
                        site=str(job["site"]),
                        job_url=str(job["job_url"]),
                        title=str(job["title"]),
                        company_name=str(job["company_name"]),
                        location=str(job["location"]),
                        description=str(job["description"]),
                        skills=list(job["skills"]),
                        why_apply="Strong backend match.",
                        risks=["Salary not specified."],
                        fit_level="high",
                        source_queries=list(job.get("source_queries", [])),
                    )
                    for job in batch_jobs
                ],
                "notes": ["Batch processed."],
            },
        )()


def test_search_job_graph_runs_parallel_search_and_unification(monkeypatch) -> None:
    monkeypatch.setattr(
        search_job_nodes,
        "get_langchain_search_job_service",
        lambda: FakeSiteAgentService(),
    )
    monkeypatch.setattr(
        search_job_nodes,
        "get_gemini_job_search_service",
        lambda: FakeGeminiJobSearchService(),
    )
    graph = build_search_job_graph()

    result = asyncio.run(
        graph.ainvoke(
            {
                "status": "queued",
                "user_id": "user-1",
                "onboarding_session_id": "session-1",
                "search_strategy_summary": "Focus on remote backend roles.",
                "hard_preferences": ["remote"],
                "soft_preferences": ["product"],
                "source_sites": ["alpha", "beta"],
                "site_results": [],
                "unified_jobs": [],
                "batch_notes": [],
            }
        )
    )

    assert result["status"] == "completed"
    assert len(result["site_results"]) == 2
    assert len(result["final_jobs"]) == 1
    assert result["final_jobs"][0].fit_level == "high"
    assert "Unified jobs returned: 1" in result["summary_markdown"]
