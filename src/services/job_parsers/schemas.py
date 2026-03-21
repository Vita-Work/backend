from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SearchIntent(BaseModel):
    role: str
    search_text: str | None = None
    keywords_include: list[str] = Field(default_factory=list)
    keywords_exclude: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    remote_only: bool = False
    seniority: str | None = None
    salary_from: int | None = None


class SiteQueryPlan(BaseModel):
    site: str
    terms: list[str] = Field(default_factory=list)
    search_urls: list[str] = Field(default_factory=list)


class VacancySeed(BaseModel):
    job_url: str
    title: str | None = None
    company_name: str | None = None
    company_url: str | None = None
    published_at: str | None = None
    salary_text: str | None = None
    location: str | None = None
    raw_meta: dict[str, Any] = Field(default_factory=dict)


class ListingPageResult(BaseModel):
    vacancies: list[VacancySeed] = Field(default_factory=list)
    next_page_url: str | None = None


class VacancyDetail(BaseModel):
    title: str | None = None
    company_name: str | None = None
    company_url: str | None = None
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
    company_about: str | None = None
    company_contacts: list[str] = Field(default_factory=list)
    raw_meta: dict[str, Any] = Field(default_factory=dict)


class CompanyDetail(BaseModel):
    company_name: str | None = None
    company_url: str | None = None
    company_about: str | None = None
    company_contacts: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    raw_meta: dict[str, Any] = Field(default_factory=dict)


class VacancyRecord(BaseModel):
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
    raw_meta: dict[str, Any] = Field(default_factory=dict)


class ScrapeError(BaseModel):
    stage: str
    url: str | None = None
    message: str


class ScrapeRunResult(BaseModel):
    site: str
    status: Literal["ok", "skipped", "failed"]
    skip_reason: str | None = None
    vacancies: list[VacancyRecord] = Field(default_factory=list)
    errors: list[ScrapeError] = Field(default_factory=list)
    query_plan: SiteQueryPlan
    pages_crawled: int = 0
