import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_liveness(async_client: AsyncClient):
    response = await async_client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "alive"}


@pytest.mark.asyncio
async def test_security_headers_and_correlation(async_client: AsyncClient):
    response = await async_client.get("/health/live")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "default-src" in response.headers["Content-Security-Policy"]


@pytest.mark.asyncio
async def test_metrics_endpoint(async_client: AsyncClient):
    response = await async_client.get("/metrics")
    assert response.status_code == 200
    assert b"http_requests_total" in response.content
