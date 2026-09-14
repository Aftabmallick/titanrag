from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateACLGroupRequest(BaseModel):
    name: str = Field(..., max_length=100)
    description: str | None = Field(None, max_length=255)


class UpdateACLGroupRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class ACLGroupMemberResponse(BaseModel):
    id: UUID
    group_id: UUID
    user_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ACLGroupResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    workspace_id: UUID
    name: str
    description: str | None = None
    is_default: bool
    created_at: datetime
    member_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class AddGroupMemberRequest(BaseModel):
    user_id: UUID
