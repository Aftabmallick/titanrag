from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from titan_backend.core.config import settings
from titan_backend.core.security import create_access_token


@pytest.mark.asyncio
async def test_scim_auth_rejection(async_client: AsyncClient):
    # No auth header -> 401
    resp = await async_client.get("/api/v1/scim/v2/Users")
    assert resp.status_code == 401

    # Wrong bearer token -> 403
    resp2 = await async_client.get(
        "/api/v1/scim/v2/Users",
        headers={"Authorization": "Bearer wrong-token-123"},
    )
    assert resp2.status_code == 403


@pytest.mark.asyncio
async def test_scim_list_users_with_valid_token(async_client: AsyncClient):
    headers = {"Authorization": f"Bearer {settings.SCIM_BEARER_TOKEN}"}
    resp = await async_client.get("/api/v1/scim/v2/Users", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "Resources" in data
    assert "totalResults" in data
    assert "urn:ietf:params:scim:api:messages:2.0:ListResponse" in data["schemas"]


@pytest.mark.asyncio
async def test_scim_create_and_deactivate_user(async_client: AsyncClient, mock_db_session):
    headers = {"Authorization": f"Bearer {settings.SCIM_BEARER_TOKEN}"}

    # 1. Create user via SCIM
    create_payload = {
        "userName": "alice.okta@enterprise.com",
        "name": {"formatted": "Alice Okta"},
        "active": True,
    }
    resp = await async_client.post(
        "/api/v1/scim/v2/Users",
        json=create_payload,
        headers=headers,
    )
    assert resp.status_code == 201
    user_data = resp.json()
    assert user_data["userName"] == "alice.okta@enterprise.com"
    assert user_data["active"] is True
    user_id = user_data["id"]

    # 2. Mock user lookup for patch
    from titan_backend.db.models.users import User

    mock_user = User(
        id=UUID(user_id),
        email="alice.okta@enterprise.com",
        is_active=True,
    )
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_user

    # 3. Deactivate user via SCIM PATCH
    patch_payload = {
        "Operations": [
            {
                "op": "replace",
                "value": {"active": False},
            }
        ]
    }
    patch_resp = await async_client.patch(
        f"/api/v1/scim/v2/Users/{user_id}",
        json=patch_payload,
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["active"] is False


@pytest.mark.asyncio
async def test_scim_groups_crud_flow(async_client: AsyncClient, mock_db_session):
    headers = {"Authorization": f"Bearer {settings.SCIM_BEARER_TOKEN}"}

    # 1. Create SCIM Group
    group_payload = {
        "displayName": "DataEngineering",
        "members": [{"value": str(uuid4()), "display": "eng1@corp.com"}],
    }
    resp = await async_client.post(
        "/api/v1/scim/v2/Groups",
        json=group_payload,
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["displayName"] == "DataEngineering"
    group_id = data["id"]

    # 2. Mock group lookup
    from titan_backend.db.models.acl import ACLGroup

    mock_group = ACLGroup(
        id=UUID(group_id),
        tenant_id=uuid4(),
        workspace_id=uuid4(),
        name="DataEngineering",
        is_default=False,
    )
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_group

    # 3. Patch SCIM Group (rename)
    patch_resp = await async_client.patch(
        f"/api/v1/scim/v2/Groups/{group_id}",
        json={"Operations": [{"op": "replace", "value": {"displayName": "MLOpsEngineering"}}]},
        headers=headers,
    )
    assert patch_resp.status_code == 200

    # 4. Delete SCIM Group
    del_resp = await async_client.delete(
        f"/api/v1/scim/v2/Groups/{group_id}",
        headers=headers,
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_instant_session_revocation_on_deactivation(async_client: AsyncClient):
    """
    Verifies that when a user is deactivated in Redis (<50ms), their active
    JWT access token is immediately rejected with 401 ACCOUNT_DEACTIVATED.
    """
    user_id = uuid4()
    tenant_id = uuid4()
    token, _ = create_access_token(user_id=user_id, tenant_id=tenant_id, email="victim@corp.com")

    with patch("titan_backend.core.dependencies.get_redis_client", new_callable=AsyncMock) as mock_redis_getter:
        mock_redis = AsyncMock()
        mock_redis_getter.return_value = mock_redis

        # First request: not deactivated, token valid
        mock_redis.get.return_value = None
        resp1 = await async_client.get(
            "/api/v1/workspaces",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp1.status_code in {200, 404}

        # User is deactivated via SCIM deprovisioning
        mock_redis.get.return_value = b"1"
        resp2 = await async_client.get(
            "/api/v1/workspaces",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 401
        assert resp2.json()["error"]["code"] == "ACCOUNT_DEACTIVATED"
