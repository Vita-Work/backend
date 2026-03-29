from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class BillingEntitlementsResponse(BaseModel):
    plan_code: Literal["free", "pro"]
    plan_label: str
    access_plan_code: Literal["free", "pro_search", "weekly_sprint"]
    access_plan_label: str
    can_access_full_results: bool
    can_use_daily_monitoring: bool
    can_run_match_gap_reports: bool = False
    can_generate_job_packs: bool = False
    search_results_limit: int | None = None
    free_match_gap_limit: int | None = None
    remaining_job_pack_credits: int = 0
    included_job_pack_credits_per_period: int = 0
    top_up_job_pack_credits: int = 0
    active_pass_ends_at: datetime | None = None


class BillingSubscriptionSummaryResponse(BaseModel):
    provider: str | None = None
    status: str | None = None
    provider_customer_id: str | None = None
    provider_subscription_id: str | None = None
    provider_price_id: str | None = None
    cancel_at_period_end: bool = False
    current_period_starts_at: datetime | None = None
    current_period_ends_at: datetime | None = None
    next_billed_at: datetime | None = None
    monitoring_enabled: bool = False
    monitoring_hour_local: int = 9
    monitoring_minute_local: int = 0
    monitoring_last_run_local_date: date | None = None


class BillingAccessPassSummaryResponse(BaseModel):
    pass_type: str | None = None
    status: str | None = None
    provider_transaction_id: str | None = None
    provider_price_id: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class BillingCheckoutConfigResponse(BaseModel):
    provider: str = "paddle"
    environment: Literal["sandbox", "production"]
    enabled: bool
    client_side_token: str | None = None
    product_id: str | None = None
    price_id: str | None = None
    product_name: str | None = None
    price_label: str | None = None
    weekly_sprint_price_id: str | None = None
    weekly_sprint_product_id: str | None = None
    weekly_sprint_price_label: str | None = None
    tailor_pack_price_id: str | None = None
    tailor_pack_product_id: str | None = None
    tailor_pack_price_label: str | None = None


class BillingOverviewResponse(BaseModel):
    entitlements: BillingEntitlementsResponse
    subscription: BillingSubscriptionSummaryResponse
    access_pass: BillingAccessPassSummaryResponse = Field(
        default_factory=BillingAccessPassSummaryResponse
    )
    checkout: BillingCheckoutConfigResponse
    monitoring_timezone: str
    monitoring_schedule_local_label: str


class BillingPreferencesUpdateRequest(BaseModel):
    monitoring_enabled: bool | None = None
    monitoring_hour_local: int | None = Field(default=None, ge=0, le=23)


class PaddleWebhookResponse(BaseModel):
    success: bool = True
