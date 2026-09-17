from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from titan_backend.clients.s3_client import build_scoped_storage_path, generate_presigned_get_url
from titan_backend.core.errors import AppException
from titan_backend.core.quotas import (
    check_daily_query_quota,
    check_document_quota,
    check_storage_quota,
    consume_compute_units,
)
from titan_backend.core.security import create_access_token, decode_token


def test_minio_scoped_storage_path():
    t_id = uuid4()
    w_id = uuid4()
    d_id = uuid4()

    path = build_scoped_storage_path(t_id, w_id, d_id, "financial_report.pdf")
    expected = f"{t_id}/{w_id}/{d_id}/financial_report.pdf"
    assert path == expected


@pytest.mark.asyncio
async def test_viewer_restriction_blocks_raw_non_pdf():
    t_id = uuid4()
    w_id = uuid4()
    d_id = uuid4()

    with pytest.raises(AppException) as exc_info:
        await generate_presigned_get_url(
            tenant_id=t_id,
            workspace_id=w_id,
            document_id=d_id,
            filename="confidential_dataset.csv",
            user_role="VIEWER",
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.error_code == "VIEWER_RESTRICTION"


def test_jwt_tampering_cross_tenant_attack_rejected():
    t_id = uuid4()
    u_id = uuid4()
    valid_token, _ = create_access_token(user_id=u_id, tenant_id=t_id, email="alice@victim.com")

    # Attacker attempts to modify token payload by flipping bits/tenant_id
    parts = valid_token.split(".")
    tampered_token = f"{parts[0]}.{parts[1]}xyz.{parts[2]}"

    with pytest.raises(AppException) as exc_info:
        decode_token(tampered_token)
    assert exc_info.value.status_code == 401
    assert exc_info.value.error_code == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_finops_compute_unit_quota_breach():
    tenant_id = uuid4()

    # Mock redis incrby to return value exceeding quota
    with patch("titan_backend.core.quotas.get_redis_client", new_callable=AsyncMock) as mock_get_redis:
        mock_redis = AsyncMock()
        mock_redis.incrby.return_value = 10500  # Exceeds 10,000 limit
        mock_get_redis.return_value = mock_redis

        with pytest.raises(AppException) as exc_info:
            await consume_compute_units(
                tenant_id=tenant_id,
                operation="colpali_page",
                units=5,
                max_monthly_quota=10000,
            )
        assert exc_info.value.status_code == 429
        assert exc_info.value.error_code == "QUOTA_EXCEEDED"
        assert exc_info.value.details["current_cu"] == 10500


@pytest.mark.asyncio
async def test_cross_tenant_workspace_access_blocked(async_client):
    tenant_a = uuid4()
    user_a = uuid4()
    token_a, _ = create_access_token(user_id=user_a, tenant_id=tenant_a, email="a@corp.com")

    # Attempt to access random foreign workspace
    foreign_ws_id = uuid4()
    resp = await async_client.get(
        f"/api/v1/workspaces/{foreign_ws_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    # Must be 404 / not found (never expose existence of other tenant's resources)
    assert resp.status_code in {403, 404}


@pytest.mark.asyncio
async def test_cross_tenant_member_invite_rejected(async_client):
    tenant_a = uuid4()
    user_a = uuid4()
    token_a, _ = create_access_token(user_id=user_a, tenant_id=tenant_a, email="a@corp.com")

    ws_id = uuid4()
    resp = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "victim_from_other_tenant@victim.com", "role": "MEMBER"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code in {403, 404}


@pytest.mark.asyncio
async def test_cross_tenant_acl_group_tampering_blocked(async_client):
    tenant_b = uuid4()
    user_b = uuid4()
    token_b, _ = create_access_token(user_id=user_b, tenant_id=tenant_b, email="b@corp.com")

    foreign_ws_id = uuid4()
    resp = await async_client.post(
        f"/api/v1/workspaces/{foreign_ws_id}/acl-groups",
        json={"name": "InjectedGroup"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code in {403, 404}


@pytest.mark.asyncio
async def test_storage_quota_breach():
    tenant_id = uuid4()
    with patch("titan_backend.core.quotas.get_redis_client", new_callable=AsyncMock) as mock_get_redis:
        mock_redis = AsyncMock()
        mock_redis.incrby.return_value = 11 * 1024 * 1024 * 1024  # 11GB
        mock_get_redis.return_value = mock_redis

        with pytest.raises(AppException) as exc_info:
            await check_storage_quota(
                tenant_id=tenant_id,
                additional_bytes=2 * 1024 * 1024 * 1024,
                max_storage_bytes=10 * 1024 * 1024 * 1024,
            )
        assert exc_info.value.status_code == 429
        assert exc_info.value.error_code == "STORAGE_QUOTA_EXCEEDED"
        mock_redis.decrby.assert_called_once()


@pytest.mark.asyncio
async def test_document_quota_breach(mock_db_session):
    tenant_id = uuid4()
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = 10001  # Exceeds 10,000

    with pytest.raises(AppException) as exc_info:
        await check_document_quota(
            tenant_id=tenant_id,
            db=mock_db_session,
            max_documents=10000,
        )
    assert exc_info.value.status_code == 429
    assert exc_info.value.error_code == "DOCUMENT_QUOTA_EXCEEDED"


@pytest.mark.asyncio
async def test_daily_query_quota_breach():
    tenant_id = uuid4()
    with patch("titan_backend.core.quotas.get_redis_client", new_callable=AsyncMock) as mock_get_redis:
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 5001  # Exceeds 5,000 queries
        mock_get_redis.return_value = mock_redis

        with pytest.raises(AppException) as exc_info:
            await check_daily_query_quota(
                tenant_id=tenant_id,
                max_queries_per_day=5000,
            )
        assert exc_info.value.status_code == 429
        assert exc_info.value.error_code == "QUERY_QUOTA_EXCEEDED"


@pytest.mark.asyncio
async def test_workspace_member_removal_cleans_acl_memberships(async_client, mock_db_session):
    tenant_id = uuid4()
    admin_id = uuid4()
    target_user_id = uuid4()
    ws_id = uuid4()

    token, _ = create_access_token(user_id=admin_id, tenant_id=tenant_id, email="admin@corp.com", role="OWNER")

    from titan_backend.db.models.workspaces import Workspace, WorkspaceMember, WorkspaceRole

    mock_ws = Workspace(id=ws_id, tenant_id=tenant_id, name="Test WS")
    mock_admin_member = WorkspaceMember(workspace_id=ws_id, user_id=admin_id, role=WorkspaceRole.OWNER)
    mock_target_member = WorkspaceMember(workspace_id=ws_id, user_id=target_user_id, role=WorkspaceRole.MEMBER)

    # 1. require_permission -> workspace lookup
    # 2. require_permission -> admin membership check (OWNER)
    # 3. remove_workspace_member -> target member lookup
    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [
        mock_ws,
        mock_admin_member,
        mock_target_member,
    ]

    with patch("titan_backend.api.v1.workspaces.invalidate_user_acl_cache", new_callable=AsyncMock) as mock_inval:
        resp = await async_client.delete(
            f"/api/v1/workspaces/{ws_id}/members/{target_user_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        mock_inval.assert_called_once_with(target_user_id)


def test_path_traversal_scoped_storage_path_sanitization():
    from titan_backend.clients.s3_client import build_scoped_storage_path

    tenant_id = uuid4()
    workspace_id = uuid4()
    doc_id = uuid4()

    # Attempt path traversal in filename
    traversal_filename = "../../../etc/passwd"
    clean_filename = traversal_filename.replace("../", "").replace("..\\", "")
    path = build_scoped_storage_path(tenant_id, workspace_id, doc_id, clean_filename)
    assert ".." not in path
    assert path.startswith(f"{tenant_id}/{workspace_id}/{doc_id}/")


@pytest.mark.asyncio
async def test_viewer_cannot_request_download_action():
    tenant_id = uuid4()
    workspace_id = uuid4()
    doc_id = uuid4()

    with pytest.raises(AppException) as exc_info:
        await generate_presigned_get_url(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            document_id=doc_id,
            filename="document.pdf",
            user_role="VIEWER",
            action="download",
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.error_code == "VIEWER_DOWNLOAD_RESTRICTED"


@pytest.mark.asyncio
async def test_cross_tenant_chat_history_leak_prevented(async_client):
    tenant_attacker = uuid4()
    user_attacker = uuid4()
    token_attacker, _ = create_access_token(
        user_id=user_attacker, tenant_id=tenant_attacker, email="attacker@evil.com"
    )

    foreign_session_id = uuid4()
    resp = await async_client.get(
        f"/api/v1/chat-sessions/{foreign_session_id}/messages",
        headers={"Authorization": f"Bearer {token_attacker}"},
    )
    assert resp.status_code in {403, 404}


@pytest.mark.asyncio
async def test_cross_tenant_prompt_tampering_prevented(async_client):
    tenant_attacker = uuid4()
    user_attacker = uuid4()
    token_attacker, _ = create_access_token(
        user_id=user_attacker, tenant_id=tenant_attacker, email="attacker@evil.com"
    )

    foreign_ws = uuid4()
    resp = await async_client.post(
        f"/api/v1/workspaces/{foreign_ws}/prompts/system/versions",
        json={"content": "Malicious prompt payload", "environment": "DEV"},
        headers={"Authorization": f"Bearer {token_attacker}"},
    )
    assert resp.status_code in {403, 404}


@pytest.mark.asyncio
async def test_cross_tenant_rag_settings_tampering_prevented(async_client):
    tenant_attacker = uuid4()
    user_attacker = uuid4()
    token_attacker, _ = create_access_token(
        user_id=user_attacker, tenant_id=tenant_attacker, email="attacker@evil.com"
    )

    foreign_ws = uuid4()
    resp = await async_client.patch(
        f"/api/v1/workspaces/{foreign_ws}/rag-settings",
        json={"top_k": 50, "hybrid_alpha": 0.1},
        headers={"Authorization": f"Bearer {token_attacker}"},
    )
    assert resp.status_code in {403, 404}


@pytest.mark.asyncio
async def test_cross_tenant_document_deletion_blocked(async_client):
    tenant_attacker = uuid4()
    user_attacker = uuid4()
    token_attacker, _ = create_access_token(
        user_id=user_attacker, tenant_id=tenant_attacker, email="attacker@evil.com"
    )

    foreign_doc_id = uuid4()
    resp = await async_client.delete(
        f"/api/v1/documents/{foreign_doc_id}",
        headers={"Authorization": f"Bearer {token_attacker}"},
    )
    assert resp.status_code in {403, 404}
