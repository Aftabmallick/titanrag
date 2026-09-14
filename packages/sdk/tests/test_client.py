import httpx
import pytest
from titanrag.client import TitanRAGClient, TitanRAGError


def mock_handler(request: httpx.Request) -> httpx.Response:
    url_str = str(request.url)
    if url_str.endswith("/health/live"):
        return httpx.Response(200, json={"status": "alive"})
    elif url_str.endswith("/health/ready"):
        if request.headers.get("X-Simulate-Error"):
            return httpx.Response(
                503,
                json={
                    "error": {
                        "code": "SERVICE_UNAVAILABLE",
                        "message": "Storage unavailable",
                        "details": {},
                        "request_id": "test-123",
                    }
                },
            )
        return httpx.Response(
            200,
            json={
                "status": "ready",
                "dependencies": {
                    "postgres": {"status": "ok", "latency_ms": 1.2},
                    "qdrant": {"status": "ok", "latency_ms": 2.1},
                },
            },
        )
    elif url_str.endswith("/metrics"):
        return httpx.Response(200, text="# HELP http_requests_total\nhttp_requests_total 10\n")
    return httpx.Response(404, json={"error": {"code": "NOT_FOUND", "message": "Not Found"}})


@pytest.mark.asyncio
async def test_sdk_health_live():
    transport = httpx.MockTransport(mock_handler)
    async with TitanRAGClient(base_url="http://testserver/api/v1") as client:
        client._client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
        res = await client.get_health_live()
        assert res == {"status": "alive"}


@pytest.mark.asyncio
async def test_sdk_health_ready():
    transport = httpx.MockTransport(mock_handler)
    async with TitanRAGClient(base_url="http://testserver/api/v1") as client:
        client._client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
        res = await client.get_health_ready()
        assert res["status"] == "ready"
        assert res["dependencies"]["postgres"]["status"] == "ok"


@pytest.mark.asyncio
async def test_sdk_metrics():
    transport = httpx.MockTransport(mock_handler)
    async with TitanRAGClient(base_url="http://testserver/api/v1") as client:
        client._client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
        metrics = await client.get_metrics()
        assert "http_requests_total" in metrics


@pytest.mark.asyncio
async def test_sdk_error_handling():
    transport = httpx.MockTransport(mock_handler)
    async with TitanRAGClient(base_url="http://testserver/api/v1", api_key="rg_test") as client:
        client._client = httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            headers={"X-Simulate-Error": "true"},
        )
        with pytest.raises(TitanRAGError) as exc_info:
            await client.get_health_ready()
        assert exc_info.value.status_code == 503
        assert exc_info.value.message == "Storage unavailable"
