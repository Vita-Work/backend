from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RequestEmailCodeRequest(BaseModel):
    email: str


class VerifyEmailCodeRequest(BaseModel):
    email: str
    code: str
    timezone: str = "UTC"
    locale: str | None = None
    full_name: str | None = None


class AdminLoginRequest(BaseModel):
    email: str
    password: str


class AuthSessionUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str | None
    full_name: str | None
    timezone: str
    locale: str | None
    role: str
    status: str
    email_verified_at: datetime | None


class AuthSessionResponse(BaseModel):
    authenticated: bool
    role: str | None = None
    user: AuthSessionUserResponse | None = None
    is_new_user: bool | None = None
    next_route: str | None = None
    needs_onboarding: bool | None = None
    has_active_onboarding_session: bool | None = None
    has_completed_onboarding: bool | None = None
    has_search_results: bool | None = None
    has_tracker_jobs: bool | None = None


class GenericAcceptedResponse(BaseModel):
    detail: str


class LogoutResponse(BaseModel):
    detail: str
