import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_404_error_contract(async_client: AsyncClient):
    response = await async_client.get("/api/v1/non-existent-route")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    error = data["error"]
    assert error["code"] == "NOT_FOUND"
    assert "request_id" in error
    assert isinstance(error["request_id"], str)
    assert len(error["request_id"]) > 0
