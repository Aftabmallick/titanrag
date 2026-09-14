from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from titan_backend.core.dependencies import CurrentUser, get_current_user
from titan_backend.db.models.chat import ChatSession
from titan_backend.db.models.workspaces import Workspace, WorkspaceMember, WorkspaceRole
from titan_backend.main import app


@pytest.fixture
def test_member_user() -> CurrentUser:
    return CurrentUser(
        id=uuid4(),
        tenant_id=uuid4(),
        email="member@corp.com",
        scopes=["*"],
    )


@pytest.mark.asyncio
async def test_chat_chitchat_fast_path(async_client, mock_db_session, test_member_user):
    ws_id = uuid4()
    mock_ws = Workspace(id=ws_id, tenant_id=test_member_user.tenant_id, name="Test WS", settings={})
    mock_member = WorkspaceMember(workspace_id=ws_id, user_id=test_member_user.id, role=WorkspaceRole.MEMBER)

    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [mock_ws, mock_member]
    app.dependency_overrides[get_current_user] = lambda: test_member_user

    payload = {
        "query": "Hello! How are you?",
    }

    # Patch preflight_chat_quota to avoid Redis dependency in unit test
    with patch("titan_backend.api.v1.chat.preflight_chat_quota", new_callable=AsyncMock):
        resp = await async_client.post(f"/api/v1/workspaces/{ws_id}/chat", json=payload)
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        body = resp.text
        assert "event: token" in body
        assert "Hello!" in body
        assert "event: done" in body


@pytest.mark.asyncio
async def test_chat_meta_fast_path(async_client, mock_db_session, test_member_user):
    ws_id = uuid4()
    mock_ws = Workspace(id=ws_id, tenant_id=test_member_user.tenant_id, name="Test WS", settings={})
    mock_member = WorkspaceMember(workspace_id=ws_id, user_id=test_member_user.id, role=WorkspaceRole.MEMBER)

    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [mock_ws, mock_member]
    app.dependency_overrides[get_current_user] = lambda: test_member_user

    payload = {
        "query": "What can you do?",
    }

    with patch("titan_backend.api.v1.chat.preflight_chat_quota", new_callable=AsyncMock):
        resp = await async_client.post(f"/api/v1/workspaces/{ws_id}/chat", json=payload)
        assert resp.status_code == 200
        body = resp.text
        assert "event: token" in body
        assert "TitanRAG" in body


@pytest.mark.asyncio
async def test_chat_session_lifecycle(async_client, mock_db_session, test_member_user):
    ws_id = uuid4()
    mock_ws = Workspace(id=ws_id, tenant_id=test_member_user.tenant_id, name="Test WS", settings={})
    mock_member = WorkspaceMember(workspace_id=ws_id, user_id=test_member_user.id, role=WorkspaceRole.MEMBER)

    session_id = uuid4()
    mock_session = ChatSession(
        id=session_id,
        tenant_id=test_member_user.tenant_id,
        workspace_id=ws_id,
        user_id=test_member_user.id,
        title="Project Research",
        meta={},
    )

    app.dependency_overrides[get_current_user] = lambda: test_member_user

    # 1. Create Session
    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [mock_ws, mock_member]
    create_resp = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/chat-sessions",
        json={"title": "Project Research"},
    )
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    assert created_data["title"] == "Project Research"

    # 2. List Sessions
    mock_db_session.execute.return_value.all.return_value = [(mock_session, 2)]
    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [mock_ws, mock_member]
    list_resp = await async_client.get(f"/api/v1/workspaces/{ws_id}/chat-sessions")
    assert list_resp.status_code == 200
    sessions_list = list_resp.json()
    assert len(sessions_list) >= 1

    # 3. Rename Session
    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [
        mock_ws,
        mock_member,
        mock_session,
    ]
    patch_resp = await async_client.patch(
        f"/api/v1/workspaces/{ws_id}/chat-sessions/{session_id}",
        json={"title": "Updated Research Title"},
    )
    assert patch_resp.status_code == 200

    # 4. Delete Session
    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [
        mock_ws,
        mock_member,
        mock_session,
    ]
    del_resp = await async_client.delete(f"/api/v1/workspaces/{ws_id}/chat-sessions/{session_id}")
    assert del_resp.status_code == 204
