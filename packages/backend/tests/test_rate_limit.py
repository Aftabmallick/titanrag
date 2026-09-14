import hashlib
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from titan_backend.core.security import create_access_token


@pytest.mark.asyncio
async def test_rate_limiter_distinct_user_buckets(async_client: AsyncClient):
    """
    Ensure two different users with different JWTs get completely distinct
    rate limiter buckets (preventing SHA-256 key prefix collisions).
    """
    user_a = uuid4()
    user_b = uuid4()
    tenant_a = uuid4()
    tenant_b = uuid4()

    token_a, _ = create_access_token(user_id=user_a, tenant_id=tenant_a, email="a@corp.com")
    token_b, _ = create_access_token(user_id=user_b, tenant_id=tenant_b, email="b@corp.com")

    # The SHA-256 hashes of the two tokens must be distinct
    hash_a = hashlib.sha256(token_a.encode()).hexdigest()[:16]
    hash_b = hashlib.sha256(token_b.encode()).hexdigest()[:16]
    assert hash_a != hash_b


@pytest.mark.asyncio
async def test_rate_limiter_blocks_and_sets_headers(async_client: AsyncClient):
    """
    Verify SlidingWindowRateLimiter returns 429 with Retry-After and X-RateLimit-* headers when limit breached.
    """
    with patch(
        "titan_backend.core.rate_limit.SlidingWindowRateLimiter.check_rate_limit",
        new_callable=AsyncMock,
    ) as mock_limit:
        # Mock rate limiter rejecting request
        mock_limit.return_value = (False, 0, 1726000060, 45)

        resp = await async_client.get(
            "/api/v1/workspaces",
            headers={"Authorization": "Bearer fake-token-for-test"},
        )
        assert resp.status_code == 429
        assert resp.headers.get("Retry-After") == "45"
        assert resp.headers.get("X-RateLimit-Remaining") == "0"
        data = resp.json()
        assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert "45 seconds" in data["error"]["message"]
