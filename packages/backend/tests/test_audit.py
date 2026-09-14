from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from titan_backend.clients.s3_client import generate_presigned_get_url
from titan_backend.core.audit import record_audit_event
from titan_backend.core.security import create_access_token


@pytest.mark.asyncio
async def test_record_audit_event(mock_db_session):
    tenant_id = uuid4()
    user_id = uuid4()

    entry = await record_audit_event(
        session=mock_db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        action="WORKSPACE_CREATE",
        resource_type="workspace",
        resource_id=str(uuid4()),
        details={"name": "Engineering"},
        ip_address="192.168.1.10",
    )
    assert entry.tenant_id == tenant_id
    assert entry.action == "WORKSPACE_CREATE"
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_presigned_url_generates_audit_entry(mock_db_session):
    tenant_id = uuid4()
    workspace_id = uuid4()
    document_id = uuid4()
    user_id = uuid4()

    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
        mock_thread.return_value = "https://minio.local/signed-url"

        url = await generate_presigned_get_url(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            document_id=document_id,
            filename="financials.pdf",
            user_role="MEMBER",
            user_id=user_id,
            action="view",
            db=mock_db_session,
            ip_address="10.0.0.1",
        )
        assert url == "https://minio.local/signed-url"
        mock_db_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_admin_query_audit_logs(async_client: AsyncClient, mock_db_session):
    tenant_id = uuid4()
    admin_id = uuid4()
    token, _ = create_access_token(user_id=admin_id, tenant_id=tenant_id, email="admin@corp.com", role="OWNER")

    resp = await async_client.get(
        "/api/v1/admin/audit-log",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
