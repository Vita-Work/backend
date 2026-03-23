from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SearchJobContext(BaseModel):
    """Stable downstream contract produced after search_setup completion."""

    user_id: str
    onboarding_session_id: str
    search_strategy_summary: str
    hard_preferences: list[str] = Field(default_factory=list)
    soft_preferences: list[str] = Field(default_factory=list)


class SiteJobListing(BaseModel):
    """Compact job listing returned by the site listing tool."""

    site: str
    title: str | None = None
    company_name: str | None = None
    location: str | None = None
    salary_text: str | None = None
    published_at: str | None = None
    job_url: str
    company_url: str | None = None


class SiteJobDetail(BaseModel):
    """Detailed normalized job payload returned by the details tool."""

    site: str
    job_url: str
    title: str | None = None
    company_name: str | None = None
    location: str | None = None
    salary_text: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    employment_type: str | None = None
    published_at: str | None = None
    description: str | None = None
    skills: list[str] = Field(default_factory=list)
    apply_url: str | None = None
    company_url: str | None = None
    company_about: str | None = None
    company_contacts: list[str] = Field(default_factory=list)
    raw_meta: dict[str, object] = Field(default_factory=dict)


class UnifiedJob(BaseModel):
    """Unified cross-site job schema for the search_job funnel."""

    site: str
    job_url: str
    title: str | None = None
    company_name: str | None = None
    location: str | None = None
    salary_text: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    employment_type: str | None = None
    published_at: str | None = None
    description: str | None = None
    skills: list[str] = Field(default_factory=list)
    apply_url: str | None = None
    company_url: str | None = None
    company_about: str | None = None
    company_contacts: list[str] = Field(default_factory=list)
    why_apply: str
    risks: list[str] = Field(default_factory=list)
    fit_level: Literal["low", "middle", "high"]
    source_queries: list[str] = Field(default_factory=list)


class SiteAgentResult(BaseModel):
    """Structured output expected from a per-site search agent."""

    site: str
    status: Literal["ok", "skipped", "failed"]
    reason: str | None = None
    queries_used: list[str] = Field(default_factory=list)
    listings_seen: list[SiteJobListing] = Field(default_factory=list)
    selected_jobs: list[SiteJobDetail] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class UnifiedJobsReport(BaseModel):
    """Final aggregated report after all site agents finish."""

    summary_markdown: str
    jobs: list[UnifiedJob] = Field(default_factory=list)
    site_results: list[SiteAgentResult] = Field(default_factory=list)
    skipped_sites: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
