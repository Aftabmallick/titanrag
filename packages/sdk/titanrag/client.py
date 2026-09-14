from typing import Any, cast

import httpx


class TitanRAGClient:
    """Official Python Client for TitanRAG Enterprise Platform."""

    def __init__(self, base_url: str = "http://localhost:8000/api/v1", api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["X-API-Key"] = api_key

    async def get_health(self) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/health/ready", headers=self.headers)
            return cast(dict[str, Any], resp.json())
