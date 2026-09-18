import re
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from bs4 import BeautifulSoup
from titan_backend.connectors.base import BaseConnector, ConnectorChange, ConnectorFile

logger = structlog.get_logger("titanrag.connectors.confluence")


def html_to_markdown(html_content: str) -> str:
    """Convert Confluence HTML content to structured Markdown text."""
    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()

    for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        level = int(h.name[1])
        h.replace_with(f"\n\n{'#' * level} {h.get_text().strip()}\n\n")

    for p in soup.find_all("p"):
        p.replace_with(f"\n\n{p.get_text().strip()}\n\n")

    for li in soup.find_all("li"):
        li.replace_with(f"\n* {li.get_text().strip()}")

    text = soup.get_text()
    return re.sub(r"\n{3,}", "\n\n", text).strip()


class ConfluenceConnector(BaseConnector):
    """
    Atlassian Confluence Cloud Connector.
    Synchronizes pages across spaces, tracks page version revisions, and extracts structured content.
    """

    def __init__(self, config: dict[str, Any], credentials: dict[str, Any]):
        super().__init__(config, credentials)
        self.base_url = self.config.get("base_url", "").rstrip("/")
        self.space_key = self.config.get("space_key")
        self.email = self.credentials.get("email", "")
        self.api_token = self.credentials.get("api_token", "")

    def _get_auth(self) -> tuple[str, str] | None:
        if self.email and self.api_token:
            return (self.email, self.api_token)
        return None

    async def test_connection(self) -> bool:
        if not self.base_url or not self.api_token:
            return False
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    f"{self.base_url}/wiki/api/v2/spaces",
                    auth=self._get_auth(),
                    params={"limit": 1},
                )
                return resp.status_code == 200
            except Exception as e:
                logger.warning("confluence_test_connection_failed", error=str(e))
                return False

    async def list_files(
        self, folder_id: str | None = None, page_token: str | None = None
    ) -> tuple[list[ConnectorFile], str | None]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            url = page_token or f"{self.base_url}/wiki/api/v2/pages"
            params: dict[str, Any] = {"limit": 50, "status": "current"}
            if self.space_key and not page_token:
                params["space-id"] = [self.space_key]

            resp = await client.get(url, auth=self._get_auth(), params=params if not page_token else None)
            if resp.status_code != 200:
                logger.error("confluence_list_pages_failed", status=resp.status_code)
                return [], None

            data = resp.json()
            next_link = data.get("_links", {}).get("next")
            if next_link and not next_link.startswith("http"):
                next_link = f"{self.base_url}{next_link}"

            results: list[ConnectorFile] = []
            for p in data.get("results", []):
                created_str = p.get("createdAt")
                mod_time = (
                    datetime.fromisoformat(created_str.replace("Z", "+00:00")) if created_str else datetime.now(UTC)
                )
                results.append(
                    ConnectorFile(
                        file_id=str(p["id"]),
                        name=f"{p.get('title', 'page')}.md",
                        mime_type="text/markdown",
                        size_bytes=len(p.get("title", "")),
                        modified_at=mod_time,
                        version=str(p.get("version", {}).get("number", 1)),
                        source_url=f"{self.base_url}/wiki{p.get('_links', {}).get('webui', '')}",
                    )
                )
            return results, next_link

    async def fetch_changes(self, cursor: dict[str, Any]) -> tuple[list[ConnectorChange], dict[str, Any]]:
        last_synced_at = cursor.get("last_synced_at")
        async with httpx.AsyncClient(timeout=15.0) as client:
            cql = f"space = '{self.space_key}'" if self.space_key else "type = 'page'"
            if last_synced_at:
                cql += f" and lastModified >= '{last_synced_at[:10]}'"

            resp = await client.get(
                f"{self.base_url}/wiki/rest/api/content/search",
                auth=self._get_auth(),
                params={"cql": cql, "limit": 50, "expand": "version,history"},
            )
            if resp.status_code != 200:
                return [], cursor

            data = resp.json()
            new_cursor = {
                "last_synced_at": datetime.now(UTC).isoformat(),
            }
            changes: list[ConnectorChange] = []
            for p in data.get("results", []):
                mod_date = p.get("version", {}).get("when")
                mod_time = datetime.fromisoformat(mod_date.replace("Z", "+00:00")) if mod_date else datetime.now(UTC)
                conn_file = ConnectorFile(
                    file_id=str(p["id"]),
                    name=f"{p.get('title', 'page')}.md",
                    mime_type="text/markdown",
                    size_bytes=1024,
                    modified_at=mod_time,
                    version=str(p.get("version", {}).get("number", 1)),
                    source_url=f"{self.base_url}/wiki{p.get('_links', {}).get('webui', '')}",
                )
                changes.append(
                    ConnectorChange(
                        file_id=str(p["id"]),
                        change_type="MODIFIED",
                        file=conn_file,
                    )
                )
            return changes, new_cursor

    async def download_file(self, file_id: str) -> tuple[bytes, str]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{self.base_url}/wiki/api/v2/pages/{file_id}",
                auth=self._get_auth(),
                params={"body-format": "storage"},
            )
            if resp.status_code != 200:
                return b"", f"page_{file_id}.md"

            data = resp.json()
            title = data.get("title", f"page_{file_id}")
            html_body = data.get("body", {}).get("storage", {}).get("value", "")
            markdown_content = f"# {title}\n\n{html_to_markdown(html_body)}"
            return markdown_content.encode("utf-8"), f"{title}.md"

    async def fetch_access_control(self, file_id: str) -> list[str]:
        # Confluence space/page permissions default to workspace members
        return []
