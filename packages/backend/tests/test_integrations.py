import hashlib
import hmac
import time
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest

from titan_backend.integrations.agent_actions import AgentActionManager
from titan_backend.integrations.email_parser import InboundEmailParser
from titan_backend.integrations.slack import build_slack_rag_response, verify_slack_signature
from titan_backend.integrations.teams import build_teams_adaptive_card
from titan_backend.integrations.webhook_dispatcher import WebhookDispatcher


def test_webhook_hmac_signing():
    payload = b'{"event":"document.ingested","document_id":"doc_123"}'
    secret = "my_super_secret_token_123"
    timestamp = 1726670000

    sig_header = WebhookDispatcher.sign_payload(payload, secret, timestamp)
    assert f"t={timestamp},v1=" in sig_header
    sig_value = sig_header.split("v1=")[1]
    assert len(sig_value) == 64  # sha256 hex


def test_slack_signature_verification():
    secret = "slack_test_signing_secret"
    body = b"command=%2Ftitan&text=What+is+our+revenue%3F"
    now_ts = str(int(time.time()))

    sig_base = f"v0:{now_ts}:{body.decode('utf-8')}".encode("utf-8")
    valid_sig = "v0=" + hmac.new(secret.encode("utf-8"), sig_base, hashlib.sha256).hexdigest()

    assert verify_slack_signature(secret, body, now_ts, valid_sig) is True
    assert verify_slack_signature(secret, body, now_ts, "v0=invalid_signature_hex") is False


def test_slack_and_teams_response_builders():
    slack_resp = build_slack_rag_response(
        query="Explain Q3 Growth",
        answer="Q3 revenue grew by 24% YoY.",
        citations=[{"title": "Q3_Report.pdf", "page_number": 3}],
        workspace_name="Finance",
    )
    assert "blocks" in slack_resp
    assert slack_resp["response_type"] == "in_channel"

    teams_card = build_teams_adaptive_card(
        query="Explain Q3 Growth",
        answer="Q3 revenue grew by 24% YoY.",
        citations=[{"title": "Q3_Report.pdf", "page_number": 3}],
        workspace_name="Finance",
    )
    assert teams_card["type"] == "message"
    assert teams_card["attachments"][0]["contentType"] == "application/vnd.microsoft.card.adaptive"


@pytest.mark.asyncio
async def test_agent_action_tools_hitl_flow():
    tools = AgentActionManager.list_available_tools()
    tool_names = [t["function"]["name"] for t in tools]
    assert "create_jira_issue" in tool_names
    assert "send_slack_notification" in tool_names
    assert "export_google_sheet" in tool_names

    # 1. Non-confirmation tool executes immediately
    slack_res = await AgentActionManager.execute_action(
        tool_name="send_slack_notification",
        arguments={"channel": "#general", "message": "All servers healthy"},
        user_id="user_1",
        workspace_id="ws_1",
    )
    assert slack_res["status"] == "executed"

    # 2. Critical tool requires confirmation
    jira_res = await AgentActionManager.execute_action(
        tool_name="create_jira_issue",
        arguments={"project_key": "SEC", "summary": "Fix CVE-2026", "description": "High priority"},
        user_id="user_1",
        workspace_id="ws_1",
    )
    assert jira_res["status"] == "requires_confirmation"
    confirm_id = jira_res["confirmation_id"]

    # 3. Confirm execution
    confirm_res = await AgentActionManager.confirm_action(confirm_id, approved=True)
    assert confirm_res["status"] == "executed"
    assert confirm_res["tool_name"] == "create_jira_issue"
