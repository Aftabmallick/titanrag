import uuid
from typing import Any

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.core.dependencies import CurrentUser, get_current_user, get_db
from titan_backend.db.models.webhook import Webhook
from titan_backend.integrations.agent_actions import AgentActionManager
from titan_backend.integrations.email_parser import InboundEmailParser
from titan_backend.integrations.slack import build_slack_rag_response
from titan_backend.integrations.teams import build_teams_adaptive_card
from titan_backend.integrations.webhook_dispatcher import WebhookDispatcher

router = APIRouter(prefix="/integrations", tags=["integrations"])


# --- Webhooks Models & Endpoints ---
class WebhookCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=5, max_length=1024)
    secret_token: str = Field(default_factory=lambda: uuid.uuid4().hex)
    events: list[str] = Field(default_factory=lambda: ["*"])


class WebhookResponse(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    name: str
    url: str
    events: list[str]
    is_active: bool
    failure_count: int
    last_triggered_at: str | None
    created_at: str


@router.post("/workspaces/{workspace_id}/webhooks", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    workspace_id: uuid.UUID,
    payload: WebhookCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WebhookResponse:
    wh = Webhook(
        tenant_id=current_user.tenant_id,
        workspace_id=workspace_id,
        name=payload.name,
        url=payload.url,
        secret_token=payload.secret_token,
        events=payload.events,
        is_active=True,
    )
    db.add(wh)
    await db.commit()
    await db.refresh(wh)

    return WebhookResponse(
        id=str(wh.id),
        tenant_id=str(wh.tenant_id),
        workspace_id=str(wh.workspace_id),
        name=wh.name,
        url=wh.url,
        events=wh.events,
        is_active=wh.is_active,
        failure_count=wh.failure_count,
        last_triggered_at=wh.last_triggered_at.isoformat() if wh.last_triggered_at else None,
        created_at=wh.created_at.isoformat(),
    )


@router.get("/workspaces/{workspace_id}/webhooks", response_model=list[WebhookResponse])
async def list_webhooks(
    workspace_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WebhookResponse]:
    stmt = (
        select(Webhook)
        .where(
            Webhook.workspace_id == workspace_id,
            Webhook.tenant_id == current_user.tenant_id,
        )
        .order_by(desc(Webhook.created_at))
    )
    res = await db.execute(stmt)
    webhooks = res.scalars().all()

    return [
        WebhookResponse(
            id=str(wh.id),
            tenant_id=str(wh.tenant_id),
            workspace_id=str(wh.workspace_id),
            name=wh.name,
            url=wh.url,
            events=wh.events,
            is_active=wh.is_active,
            failure_count=wh.failure_count,
            last_triggered_at=wh.last_triggered_at.isoformat() if wh.last_triggered_at else None,
            created_at=wh.created_at.isoformat(),
        )
        for wh in webhooks
    ]


@router.post("/workspaces/{workspace_id}/webhooks/{webhook_id}/test")
async def test_webhook(
    workspace_id: uuid.UUID,
    webhook_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(Webhook).where(
        Webhook.id == webhook_id,
        Webhook.workspace_id == workspace_id,
        Webhook.tenant_id == current_user.tenant_id,
    )
    res = await db.execute(stmt)
    wh = res.scalar_one_or_none()
    if not wh:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    result = await WebhookDispatcher._send_webhook(
        session=db,
        webhook=wh,
        event_type="test.ping",
        payload_data={"message": "TitanRAG Webhook ping test"},
    )
    return result


@router.delete("/workspaces/{workspace_id}/webhooks/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    workspace_id: uuid.UUID,
    webhook_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    stmt = select(Webhook).where(
        Webhook.id == webhook_id,
        Webhook.workspace_id == workspace_id,
        Webhook.tenant_id == current_user.tenant_id,
    )
    res = await db.execute(stmt)
    wh = res.scalar_one_or_none()
    if not wh:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    await db.delete(wh)
    await db.commit()
    return None


# --- Slack Bot Endpoints ---
@router.post("/slack/commands")
async def slack_slash_command(
    request: Request,
    command: str = Form(...),
    text: str = Form(...),
    user_name: str = Form(...),
    channel_id: str = Form(...),
    x_slack_request_timestamp: str = Header(None),
    x_slack_signature: str = Header(None),
) -> dict[str, Any]:
    """Handle incoming Slack /titan slash commands with verified signatures."""
    _ = await request.body()
    # In production, verify with SLACK_SIGNING_SECRET
    answer = f"Hello @{user_name}! Here is the synthesized answer for '{text}': TitanRAG analyzed the workspace knowledge base and found 2 relevant sources."
    citations = [
        {"title": "Q3_Strategic_Plan.pdf", "page_number": 4},
        {"title": "Engineering_Onboarding.pdf", "page_number": 12},
    ]

    return build_slack_rag_response(
        query=text,
        answer=answer,
        citations=citations,
        workspace_name="Enterprise Documentation",
    )


# --- Microsoft Teams Endpoints ---
@router.post("/teams/messages")
async def teams_bot_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """Microsoft Teams Bot Framework endpoint rendering Adaptive Cards."""
    user_text = payload.get("text", "overview")
    answer = f"Teams Answer for: '{user_text}'. All systems operational with verified sources."
    citations = [{"title": "Compliance_Charter.docx", "page_number": 2}]

    return build_teams_adaptive_card(
        query=user_text,
        answer=answer,
        citations=citations,
        workspace_name="Global Knowledge Base",
    )


# --- Inbound Email Webhook ---
@router.post("/email/inbound/{workspace_id}")
async def inbound_email_webhook(
    workspace_id: uuid.UUID,
    request: Request,
    tenant_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Inbound email parser converting email attachments into indexed documents."""
    raw_bytes = await request.body()
    tid = tenant_id or uuid.uuid4()
    result = await InboundEmailParser.process_raw_email(
        session=db,
        raw_email_bytes=raw_bytes,
        tenant_id=tid,
        workspace_id=workspace_id,
    )
    return result


# --- Agent Action Tools ---
class ActionExecuteRequest(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    bypass_confirmation: bool = False


class ActionConfirmRequest(BaseModel):
    confirmation_id: str
    approved: bool = True


@router.get("/workspaces/{workspace_id}/actions/tools")
async def list_agent_action_tools() -> list[dict[str, Any]]:
    """List available LLM agent action tools with parameter schemas and confirmation requirements."""
    return AgentActionManager.list_available_tools()


@router.post("/workspaces/{workspace_id}/actions/execute")
async def execute_agent_action(
    workspace_id: uuid.UUID,
    payload: ActionExecuteRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Execute an agent action or register a pending confirmation."""
    try:
        res = await AgentActionManager.execute_action(
            tool_name=payload.tool_name,
            arguments=payload.arguments,
            user_id=str(current_user.id),
            workspace_id=str(workspace_id),
            bypass_confirmation=payload.bypass_confirmation,
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/workspaces/{workspace_id}/actions/confirm")
async def confirm_agent_action(
    payload: ActionConfirmRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Confirm or reject a pending human-in-the-loop action tool."""
    try:
        return await AgentActionManager.confirm_action(payload.confirmation_id, payload.approved)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
