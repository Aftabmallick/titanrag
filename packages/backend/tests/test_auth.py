from datetime import timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from titan_backend.core.errors import AppException
from titan_backend.core.security import (
    create_access_token,
    decode_token,
    get_password_hash,
    verify_password,
)


def test_password_hashing_and_verification():
    raw = "SuperSecretP@ssw0rd!2026"
    hashed = get_password_hash(raw)
    assert hashed != raw
    assert verify_password(raw, hashed) is True
    assert verify_password("WrongPassword123", hashed) is False


def test_jwt_lifecycle_and_claims():
    u_id = uuid4()
    t_id = uuid4()
    token, jti = create_access_token(
        user_id=u_id,
        tenant_id=t_id,
        email="test@titanrag.io",
        role="ADMIN",
    )
    assert isinstance(token, str)
    assert len(jti) > 10

    claims = decode_token(token)
    assert claims["sub"] == str(u_id)
    assert claims["tenant_id"] == str(t_id)
    assert claims["email"] == "test@titanrag.io"
    assert claims["role"] == "ADMIN"
    assert claims["type"] == "access"
    assert claims["jti"] == jti


def test_jwt_expiration():
    u_id = uuid4()
    t_id = uuid4()
    # Expired 10 seconds ago
    token, _ = create_access_token(
        user_id=u_id,
        tenant_id=t_id,
        email="expired@titanrag.io",
        expires_delta=timedelta(seconds=-10),
    )
    with pytest.raises(AppException) as exc_info:
        decode_token(token)
    assert exc_info.value.status_code == 401
    assert exc_info.value.error_code == "TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_brute_force_account_lockout(async_client: AsyncClient):
    email = f"brute_victim_{uuid4().hex[:8]}@corp.com"

    with (
        patch("titan_backend.api.v1.auth.check_account_locked", new_callable=AsyncMock) as mock_locked,
        patch("titan_backend.api.v1.auth.record_login_failure", new_callable=AsyncMock) as mock_record,
    ):
        # 1. First 4 attempts: not locked yet
        mock_locked.return_value = (False, 0)
        mock_record.return_value = (4, False, 0)

        resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "WrongPassword"},
        )
        assert resp.status_code == 401

        # 2. 5th attempt triggers lockout
        mock_record.return_value = (5, True, 900)
        resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "WrongPassword"},
        )
        assert resp.status_code == 423
        assert "Retry-After" in resp.headers
        assert resp.headers["Retry-After"] == "900"

        # 3. Subsequent attempt is blocked by check_account_locked
        mock_locked.return_value = (True, 895)
        resp2 = await async_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "EvenCorrectPasswordNow"},
        )
        assert resp2.status_code == 423
        assert resp2.json()["error"]["code"] == "ACCOUNT_LOCKED"


@pytest.mark.asyncio
async def test_register_and_login_flow(async_client: AsyncClient, mock_db_session):
    email = "founder@startup.io"
    password = "SecurePassword2026!"

    # 1. Register
    resp = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Founder", "tenant_name": "Startup Inc"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

    # 2. Refresh tokens
    from titan_backend.db.models.users import User

    mock_user = User(
        id=uuid4(),
        tenant_id=uuid4(),
        email=email,
        is_active=True,
    )
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_user

    refresh_resp2 = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": data["refresh_token"]},
    )
    assert refresh_resp2.status_code == 200
    new_tokens = refresh_resp2.json()
    assert "access_token" in new_tokens

    # 3. Logout
    logout_resp = await async_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert logout_resp.status_code == 200
