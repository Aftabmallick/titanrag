from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateAPIKeyRequest(BaseModel):
    name: str = Field(..., max_length=255, description="Descriptive name for the API key")
    scopes: list[str] = Field(default=["read", "write"], description="Allowed scopes: read, write, admin")
    expires_in_days: int | None = Field(None, ge=1, le=365, description="Optional expiry in days")


class APIKeyResponse(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    scopes: list[str]
    is_revoked: bool
    expires_at: datetime | None = None
    created_at: datetime
    raw_key: str | None = None  # Plaintext key returned strictly once upon generation

    model_config = ConfigDict(from_attributes=True)
