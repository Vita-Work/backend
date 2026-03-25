import asyncio
from types import SimpleNamespace

from src.workflows.search_job.graph import build_search_job_graph
from src.workflows.search_job.nodes import detail_dedupe as detail_dedupe_nodes
from src.workflows.search_job.nodes import detail_fetch as detail_fetch_nodes
from src.workflows.search_job.nodes import listing_dedupe as listing_dedupe_nodes
from src.workflows.search_job.nodes import parser as parser_nodes
from src.workflows.search_job.nodes import plan as plan_nodes
from src.workflows.search_job.nodes import rank as rank_nodes
from src.workflows.search_job.schemas import (
    ListingCandidate,
    SearchExecutionPlan,
    SiteJobDetail,
    SiteJobListing,
    UnifiedJob,
)


class FakePlanService:
    model_name = "gemini/fake-dspy"

    async def build_search_job_execution_plan(
        self,
        *,
        search_strategy_summary: str,
        hard_preferences: list[str],
        soft_preferences: list[str],
        available_sites: list[str],
    ) -> SearchExecutionPlan:
        assert search_strategy_summary
        assert hard_preferences == ["remote"]
        assert soft_preferences == ["product"]
        assert available_sites == ["alpha", "beta"]
        return SearchExecutionPlan(
            queries=["python backend remote", "platform engineer remote"],
            include_keywords=["python", "backend"],
            exclude_keywords=["intern"],
            locations=[],
            remote_only=True,
            target_sites=["alpha", "beta"],
            notes=["plan ready"],
        )


class FakeToolService:
    def __init__(self, site_name: str) -> None:
        self.site_name = site_name

    def get_site_profile(self):
        return SimpleNamespace(
            site=self.site_name,
            label=self.site_name.title(),
            supports_native_query_search=True,
            allowed_countries=[],
            notes=None,
        )

    async def list_site_jobs(self, *, args):
        if self.site_name == "alpha":
            if args.search_text == "python backend remote":
                return [
                    SiteJobListing(
                        site="alpha",
                        title="Backend Engineer",
                        company_name="Acme",
                        location="Remote",
                        job_url="https://alpha.example/jobs/acme-backend",
                    )
                ]
            return [
                SiteJobListing(
                    site="alpha",
                    title="Backend Engineer",
                    company_name="Acme",
                    location="Remote",
                    job_url="https://alpha.example/jobs/acme-backend",
                )
            ]

        if args.search_text == "python backend remote":
            return [
                SiteJobListing(
                    site="beta",
                    title="Backend Engineer",
                    company_name="Acme",
                    location="Remote",
                    job_url="https://beta.example/jobs/acme-backend-duplicate",
                )
            ]
        return [
            SiteJobListing(
                site="beta",
                title="Platform Engineer",
                company_name="Beta Labs",
                location="Remote",
                job_url="https://beta.example/jobs/platform",
            )
        ]

    async def get_job_details_from_listings(self, *, listings):
        return [
            SiteJobDetail(
                site=self.site_name,
                job_url=listing.job_url,
                title=listing.title,
                company_name=listing.company_name,
                location=listing.location,
                description=f"{listing.title} with Python and distributed systems",
                skills=["Python", "FastAPI"],
                raw_meta={},
            )
            for listing in listings
        ]


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
        assert hard_preferences == ["remote"]
        assert soft_preferences == ["product"]
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
                        why_apply="Strong match.",
                        risks=["Salary not specified."],
                        fit_level="high",
                        source_queries=list(job.get("source_queries", [])),
                    )
                    for job in batch_jobs
                ],
                "notes": ["Batch processed."],
            },
        )()


class FakeEmbeddingsService:
    async def embed_texts(self, *, texts: list[str], task_type: str = "SEMANTIC_SIMILARITY"):
        _ = task_type
        return [[float(index + 1), 0.0, 0.0] for index, _ in enumerate(texts)]


def test_search_job_graph_runs_staged_pipeline(monkeypatch) -> None:
    monkeypatch.setattr(plan_nodes, "get_dspy_search_setup_service", lambda: FakePlanService())
    monkeypatch.setattr(
        parser_nodes,
        "get_job_site_tools_service",
        lambda site_name: FakeToolService(site_name),
    )
    monkeypatch.setattr(
        detail_fetch_nodes,
        "get_job_site_tools_service",
        lambda site_name: FakeToolService(site_name),
    )
    monkeypatch.setattr(
        rank_nodes,
        "get_gemini_job_search_service",
        lambda: FakeGeminiJobSearchService(),
    )
    monkeypatch.setattr(
        listing_dedupe_nodes,
        "get_gemini_embeddings_service",
        lambda: FakeEmbeddingsService(),
    )
    monkeypatch.setattr(
        detail_dedupe_nodes,
        "get_gemini_embeddings_service",
        lambda: FakeEmbeddingsService(),
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
                "listing_candidates": [],
                "detailed_jobs": [],
                "unified_jobs": [],
                "batch_notes": [],
            }
        )
    )

    assert result["status"] == "completed"
    assert result["execution_plan"].queries == [
        "python backend remote",
        "platform engineer remote",
    ]
    assert len(result["site_results"]) == 2
    assert len(result["deduped_listings"]) == 2
    assert len(result["deduped_details"]) == 2
    assert len(result["final_jobs"]) == 2
    assert "Detailed jobs kept: 2" in result["summary_markdown"]


class FakeEmptyPlanService:
    model_name = "gemini/fake-dspy"

    async def build_search_job_execution_plan(self, **kwargs) -> SearchExecutionPlan:
        _ = kwargs
        return SearchExecutionPlan()


class FakeUnsupportedToolService:
    def __init__(self, site_name: str) -> None:
        self.site_name = site_name

    def get_site_profile(self):
        return SimpleNamespace(
            site=self.site_name,
            label=self.site_name.title(),
            supports_native_query_search=False,
            allowed_countries=[],
            notes="unsupported",
        )


def test_search_job_graph_handles_empty_plan_and_unsupported_site(monkeypatch) -> None:
    monkeypatch.setattr(plan_nodes, "get_dspy_search_setup_service", lambda: FakeEmptyPlanService())
    monkeypatch.setattr(
        parser_nodes,
        "get_job_site_tools_service",
        lambda site_name: FakeUnsupportedToolService(site_name),
    )
    monkeypatch.setattr(
        detail_fetch_nodes,
        "get_job_site_tools_service",
        lambda site_name: FakeUnsupportedToolService(site_name),
    )
    monkeypatch.setattr(
        rank_nodes,
        "get_gemini_job_search_service",
        lambda: FakeGeminiJobSearchService(),
    )
    monkeypatch.setattr(
        listing_dedupe_nodes,
        "get_gemini_embeddings_service",
        lambda: FakeEmbeddingsService(),
    )
    monkeypatch.setattr(
        detail_dedupe_nodes,
        "get_gemini_embeddings_service",
        lambda: FakeEmbeddingsService(),
    )

    graph = build_search_job_graph()
    result = asyncio.run(
        graph.ainvoke(
            {
                "status": "queued",
                "user_id": "user-2",
                "onboarding_session_id": "session-2",
                "search_strategy_summary": "Search for backend roles in safe fallback mode.",
                "hard_preferences": [],
                "soft_preferences": [],
                "source_sites": ["alpha"],
                "site_results": [],
                "listing_candidates": [],
                "detailed_jobs": [],
                "unified_jobs": [],
                "batch_notes": [],
            }
        )
    )

    assert result["status"] == "completed"
    assert result["execution_plan"].queries == ["Search for backend roles in safe fallback mode."]


def test_search_job_graph_monitoring_mode_filters_previously_seen_jobs(monkeypatch) -> None:
    class FakeMonitoringPlanService:
        model_name = "gemini/fake-dspy"

        async def build_search_job_execution_plan(
            self,
            *,
            search_strategy_summary: str,
            hard_preferences: list[str],
            soft_preferences: list[str],
            available_sites: list[str],
        ) -> SearchExecutionPlan:
            assert search_strategy_summary
            assert hard_preferences == ["remote"]
            assert soft_preferences == ["product"]
            assert available_sites == ["alpha"]
            return SearchExecutionPlan(
                queries=["python backend remote"],
                include_keywords=["python", "backend", "platform"],
                exclude_keywords=["intern"],
                locations=[],
                remote_only=True,
                target_sites=["alpha"],
                notes=["plan ready"],
            )

    class FakeMonitoringToolService(FakeToolService):
        async def list_site_jobs(self, *, args):
            _ = args
            return [
                SiteJobListing(
                    site="alpha",
                    title="Backend Engineer",
                    company_name="Acme",
                    location="Remote",
                    job_url="https://alpha.example/jobs/acme-backend",
                ),
                SiteJobListing(
                    site="alpha",
                    title="Platform Engineer",
                    company_name="Beta Labs",
                    location="Remote",
                    job_url="https://alpha.example/jobs/platform",
                ),
            ]

    monkeypatch.setattr(
        plan_nodes,
        "get_dspy_search_setup_service",
        lambda: FakeMonitoringPlanService(),
    )
    monkeypatch.setattr(
        parser_nodes,
        "get_job_site_tools_service",
        lambda site_name: FakeMonitoringToolService(site_name),
    )
    monkeypatch.setattr(
        detail_fetch_nodes,
        "get_job_site_tools_service",
        lambda site_name: FakeMonitoringToolService(site_name),
    )
    monkeypatch.setattr(
        rank_nodes,
        "get_gemini_job_search_service",
        lambda: FakeGeminiJobSearchService(),
    )
    monkeypatch.setattr(
        listing_dedupe_nodes,
        "get_gemini_embeddings_service",
        lambda: FakeEmbeddingsService(),
    )
    monkeypatch.setattr(
        detail_dedupe_nodes,
        "get_gemini_embeddings_service",
        lambda: FakeEmbeddingsService(),
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
                "source_sites": ["alpha"],
                "monitoring_mode": True,
                "seen_job_urls": ["https://alpha.example/jobs/acme-backend"],
                "seen_job_fingerprints": [],
                "site_results": [],
                "listing_candidates": [],
                "detailed_jobs": [],
                "unified_jobs": [],
                "batch_notes": [],
            }
        )
    )

    assert result["status"] == "completed"
    assert len(result["final_jobs"]) == 1
    assert result["final_jobs"][0].job_url == "https://alpha.example/jobs/platform"
    assert "Monitoring mode: on" in result["summary_markdown"]
    assert result["source_sites"] == ["alpha"]


def test_listing_dedupe_semantic_layer_merges_cross_site_duplicates(monkeypatch) -> None:
    monkeypatch.setattr(
        listing_dedupe_nodes,
        "get_gemini_embeddings_service",
        lambda: FakeSemanticDuplicateEmbeddingsService(),
    )

    result = asyncio.run(
        listing_dedupe_nodes.listing_dedupe_node(
            {
                "status": "searching",
                "user_id": "user-3",
                "onboarding_session_id": "session-3",
                "search_strategy_summary": "Remote Python backend roles",
                "hard_preferences": [],
                "soft_preferences": [],
                "source_sites": ["alpha", "beta"],
                "execution_plan": SearchExecutionPlan(
                    queries=["python backend remote", "backend engineer remote"],
                    include_keywords=["python", "backend"],
                    exclude_keywords=[],
                    locations=[],
                    remote_only=True,
                    target_sites=["alpha", "beta"],
                ),
                "site_results": [],
                "listing_candidates": [
                    _listing_candidate(
                        site="alpha",
                        query="python backend remote",
                        title="Senior Python Backend Engineer",
                        company="Acme Labs",
                        url="https://alpha.example/jobs/acme-senior-backend",
                    ),
                    _listing_candidate(
                        site="beta",
                        query="backend engineer remote",
                        title="Backend Python Developer",
                        company="ACME Labs",
                        url="https://beta.example/vacancies/acme-backend-python",
                    ),
                ],
                "detailed_jobs": [],
                "unified_jobs": [],
                "batch_notes": [],
            }
        )
    )

    assert len(result["deduped_listings"]) == 1
    assert set(result["deduped_listings"][0].source_queries) == {
        "python backend remote",
        "backend engineer remote",
    }


def test_detail_dedupe_semantic_layer_merges_cross_site_duplicates(monkeypatch) -> None:
    monkeypatch.setattr(
        detail_dedupe_nodes,
        "get_gemini_embeddings_service",
        lambda: FakeSemanticDuplicateEmbeddingsService(),
    )

    result = asyncio.run(
        detail_dedupe_nodes.detail_dedupe_node(
            {
                "status": "fetching_details",
                "user_id": "user-4",
                "onboarding_session_id": "session-4",
                "search_strategy_summary": "Remote Python backend roles",
                "hard_preferences": [],
                "soft_preferences": [],
                "source_sites": ["alpha", "beta"],
                "execution_plan": SearchExecutionPlan(
                    queries=["python backend remote"],
                    include_keywords=["python", "backend"],
                    exclude_keywords=[],
                    locations=[],
                    remote_only=True,
                    target_sites=["alpha", "beta"],
                ),
                "site_results": [],
                "listing_candidates": [],
                "detailed_jobs": [
                    _detail_job(
                        site="alpha",
                        title="Senior Python Backend Engineer",
                        company="Acme Labs",
                        url="https://alpha.example/jobs/acme-senior-backend",
                    ),
                    _detail_job(
                        site="beta",
                        title="Backend Python Developer",
                        company="ACME Labs",
                        url="https://beta.example/vacancies/acme-backend-python",
                    ),
                ],
                "unified_jobs": [],
                "batch_notes": [],
            }
        )
    )

    assert len(result["deduped_details"]) == 1
    assert result["deduped_details"][0].company_name.lower() == "acme labs"


class FakeSemanticDuplicateEmbeddingsService:
    async def embed_texts(self, *, texts: list[str], task_type: str = "SEMANTIC_SIMILARITY"):
        _ = task_type
        if len(texts) != 2:
            return [[float(index + 1), 0.0, 0.0] for index, _ in enumerate(texts)]
        return [
            [1.0, 0.0, 0.0],
            [0.999, 0.001, 0.0],
        ]


def _listing_candidate(
    *,
    site: str,
    query: str,
    title: str,
    company: str,
    url: str,
) -> ListingCandidate:
    return ListingCandidate(
        site=site,
        query=query,
        job_url=url,
        title=title,
        company_name=company,
        location="Remote",
    )


def _detail_job(
    *,
    site: str,
    title: str,
    company: str,
    url: str,
) -> SiteJobDetail:
    return SiteJobDetail(
        site=site,
        job_url=url,
        title=title,
        company_name=company,
        location="Remote",
        description="Python backend services with APIs, queues, and cloud systems.",
        skills=["Python", "FastAPI", "PostgreSQL"],
        raw_meta={"source_queries": ["python backend remote"]},
    )
