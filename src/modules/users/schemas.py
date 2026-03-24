from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CreateUserRequest(BaseModel):
    """Request payload for creating a user."""

    email: str | None = None
    full_name: str | None = None
    timezone: str = "UTC"
    locale: str | None = None


class UserResponse(BaseModel):
    """Serialized user payload returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str | None
    full_name: str | None
    timezone: str
    locale: str | None
    role: str
    email_verified_at: datetime | None
    status: str
    created_at: datetime
    updated_at: datetime | None
