from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from titan_backend.db.models.plugin import HookType, PluginHealthStatus


class PluginCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Human-readable plugin name")
    slug: str | None = Field(None, min_length=2, max_length=100, description="URL-friendly slug (auto-generated if omitted)")
    description: str | None = Field(None, max_length=1000)
    version: str = Field("1.0.0", max_length=50)
    endpoint_url: str = Field(..., min_length=8, max_length=1024, description="HTTPS endpoint URL to receive webhook payloads")
    webhook_secret: str | None = Field(None, description="HMAC-SHA256 secret. Auto-generated with 256-bit entropy if not supplied.")
    hooks: list[HookType] = Field(..., min_length=1, description="List of pipeline hooks this plugin intercepts")
    timeout_ms: int = Field(2000, ge=100, le=10000, description="Timeout budget in milliseconds")
    retry_count: int = Field(1, ge=0, le=3, description="Number of retries on timeout/5xx")
    is_active: bool = Field(True, description="Whether the plugin is enabled")


class PluginUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    description: str | None = None
    endpoint_url: str | None = Field(None, min_length=8, max_length=1024)
    webhook_secret: str | None = None
    hooks: list[HookType] | None = None
    timeout_ms: int | None = Field(None, ge=100, le=10000)
    retry_count: int | None = Field(None, ge=0, le=3)
    is_active: bool | None = None


class PluginResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    workspace_id: UUID
    name: str
    slug: str
    description: str | None
    version: str
    endpoint_url: str
    webhook_secret_masked: str
    hooks: list[str]
    timeout_ms: int
    retry_count: int
    is_active: bool
    health_status: PluginHealthStatus
    last_ping_at: datetime | None
    failure_count: int
    circuit_tripped: bool
    created_at: datetime
    updated_at: datetime


class PluginCreatedResponse(PluginResponse):
    webhook_secret: str = Field(..., description="Full plaintext webhook secret (displayed ONLY upon creation)")


class PluginPingResponse(BaseModel):
    success: bool
    status_code: int | None = None
    latency_ms: float
    error: str | None = None
    circuit_tripped: bool = False


class PluginExecutionLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plugin_id: UUID
    workspace_id: UUID
    hook_type: str
    request_id: str | None
    status_code: int | None
    latency_ms: float
    error_message: str | None
    timestamp: datetime
