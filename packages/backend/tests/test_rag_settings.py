from uuid import uuid4

import pytest
from titan_backend.core.dependencies import CurrentUser, get_current_user
from titan_backend.db.models.settings import RAGSettings
from titan_backend.db.models.workspaces import Workspace, WorkspaceMember, WorkspaceRole
from titan_backend.main import app


@pytest.fixture
def test_admin_user() -> CurrentUser:
    return CurrentUser(
        id=uuid4(),
        tenant_id=uuid4(),
        email="admin@corp.com",
        scopes=["*"],
    )


@pytest.mark.asyncio
async def test_get_and_update_rag_settings(async_client, mock_db_session, test_admin_user):
    ws_id = uuid4()
    mock_ws = Workspace(id=ws_id, tenant_id=test_admin_user.tenant_id, name="Test WS", settings={})
    mock_member = WorkspaceMember(workspace_id=ws_id, user_id=test_admin_user.id, role=WorkspaceRole.ADMIN)

    settings_obj = RAGSettings(
        id=uuid4(),
        tenant_id=test_admin_user.tenant_id,
        workspace_id=ws_id,
        retrieval_mode="HYBRID",
        dense_weight=0.7,
        sparse_weight=0.3,
        top_k=20,
        rerank_top_k=5,
        score_threshold=0.40,
        context_window_strategy="HIERARCHICAL",
    )

    # 1. Test GET /settings
    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [
        mock_ws,
        mock_member,
        settings_obj,
    ]
    app.dependency_overrides[get_current_user] = lambda: test_admin_user

    resp = await async_client.get(f"/api/v1/workspaces/{ws_id}/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["retrieval_mode"] == "HYBRID"
    assert data["dense_weight"] == 0.7
    assert data["top_k"] == 20

    # 2. Test PUT /settings
    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [
        mock_ws,
        mock_member,
        settings_obj,
    ]

    update_payload = {
        "dense_weight": 0.85,
        "top_k": 30,
        "rerank_top_k": 8,
        "score_threshold": 0.55,
        "hyde_enabled": True,
    }
    put_resp = await async_client.put(f"/api/v1/workspaces/{ws_id}/settings", json=update_payload)
    assert put_resp.status_code == 200
    updated_data = put_resp.json()
    assert updated_data["dense_weight"] == 0.85
    assert updated_data["top_k"] == 30
    assert updated_data["rerank_top_k"] == 8
    assert updated_data["score_threshold"] == 0.55
    assert updated_data["hyde_enabled"] is True


@pytest.mark.asyncio
async def test_rag_settings_validation_errors(async_client, mock_db_session, test_admin_user):
    ws_id = uuid4()
    mock_ws = Workspace(id=ws_id, tenant_id=test_admin_user.tenant_id, name="Test WS", settings={})
    mock_member = WorkspaceMember(workspace_id=ws_id, user_id=test_admin_user.id, role=WorkspaceRole.ADMIN)

    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [mock_ws, mock_member]
    app.dependency_overrides[get_current_user] = lambda: test_admin_user

    # Invalid dense_weight > 1.0
    bad_payload = {"dense_weight": 1.5}
    resp = await async_client.put(f"/api/v1/workspaces/{ws_id}/settings", json=bad_payload)
    assert resp.status_code == 422
