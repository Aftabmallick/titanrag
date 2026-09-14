from unittest.mock import AsyncMock, patch

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


@pytest.mark.asyncio
async def test_readiness_all_healthy(async_client: AsyncClient):
    with (
        patch("titan_backend.api.v1.health.check_postgres_health", new_callable=AsyncMock) as mock_pg,
        patch("titan_backend.api.v1.health.check_qdrant_health", new_callable=AsyncMock) as mock_qd,
        patch("titan_backend.api.v1.health.check_redis_health", new_callable=AsyncMock) as mock_rd,
        patch("titan_backend.api.v1.health.check_minio_health", new_callable=AsyncMock) as mock_mn,
    ):
        mock_pg.return_value = True
        mock_qd.return_value = True
        mock_rd.return_value = True
        mock_mn.return_value = True

        response = await async_client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["dependencies"]["postgres"]["status"] == "ok"
        assert data["dependencies"]["qdrant"]["status"] == "ok"
        assert data["dependencies"]["redis"]["status"] == "ok"
        assert data["dependencies"]["minio"]["status"] == "ok"


@pytest.mark.asyncio
async def test_readiness_degraded(async_client: AsyncClient):
    with (
        patch("titan_backend.api.v1.health.check_postgres_health", new_callable=AsyncMock) as mock_pg,
        patch("titan_backend.api.v1.health.check_qdrant_health", new_callable=AsyncMock) as mock_qd,
        patch("titan_backend.api.v1.health.check_redis_health", new_callable=AsyncMock) as mock_rd,
        patch("titan_backend.api.v1.health.check_minio_health", new_callable=AsyncMock) as mock_mn,
    ):
        mock_pg.return_value = True
        mock_qd.return_value = False  # Qdrant down
        mock_rd.return_value = True
        mock_mn.return_value = True

        response = await async_client.get("/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["dependencies"]["qdrant"]["status"] == "down"


@pytest.mark.asyncio
async def test_readiness_quickstart_mode(async_client: AsyncClient):
    with (
        patch("titan_backend.api.v1.health.settings.QUICKSTART_MODE", True),
        patch("titan_backend.api.v1.health.check_postgres_health", new_callable=AsyncMock) as mock_pg,
        patch("titan_backend.api.v1.health.check_qdrant_health", new_callable=AsyncMock) as mock_qd,
    ):
        mock_pg.return_value = True
        mock_qd.return_value = True

        response = await async_client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["dependencies"]["redis"]["status"] == "skipped"
        assert data["dependencies"]["minio"]["status"] == "skipped"
