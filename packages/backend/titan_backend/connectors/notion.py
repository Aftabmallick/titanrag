from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from titan_backend.connectors.base import BaseConnector, ConnectorChange, ConnectorFile

logger = structlog.get_logger("titanrag.connectors.notion")


def parse_rich_text(rich_text_list: list[dict[str, Any]]) -> str:
    parts = []
    for rt in rich_text_list:
        text = rt.get("plain_text", "")
        annotations = rt.get("annotations", {})
        if annotations.get("bold"):
            text = f"**{text}**"
        if annotations.get("italic"):
            text = f"*{text}*"
        if annotations.get("code"):
            text = f"`{text}`"
        parts.append(text)
    return "".join(parts)


def block_to_markdown(block: dict[str, Any]) -> str:
    btype = block.get("type", "")
    content = block.get(btype, {})
    rich_text = content.get("rich_text", [])
    text = parse_rich_text(rich_text)

    if btype == "paragraph":
        return f"{text}\n\n"
    elif btype == "heading_1":
        return f"# {text}\n\n"
    elif btype == "heading_2":
        return f"## {text}\n\n"
    elif btype == "heading_3":
        return f"### {text}\n\n"
    elif btype == "bulleted_list_item":
        return f"* {text}\n"
    elif btype == "numbered_list_item":
        return f"1. {text}\n"
    elif btype == "to_do":
        checked = "x" if content.get("checked") else " "
        return f"- [{checked}] {text}\n"
    elif btype == "code":
        lang = content.get("language", "")
        return f"```{lang}\n{text}\n```\n\n"
    elif btype == "callout":
        return f"> [!NOTE]\n> {text}\n\n"
    elif btype == "quote":
        return f"> {text}\n\n"
    return f"{text}\n" if text else ""


class NotionConnector(BaseConnector):
    """
    Notion Workspace Connector.
    Recursively syncs Notion database pages and blocks, translating them into Markdown.
    """

    def __init__(self, config: dict[str, Any], credentials: dict[str, Any]):
        super().__init__(config, credentials)
        self.api_key = self.credentials.get("api_key", "")
        self.notion_version = "2022-06-28"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": self.notion_version,
            "Content-Type": "application/json",
        }

    async def test_connection(self) -> bool:
        if not self.api_key:
            return False
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get("https://api.notion.com/v1/users/me", headers=self._headers())
                return resp.status_code == 200
            except Exception as e:
                logger.warning("notion_test_connection_failed", error=str(e))
                return False

    async def list_files(
        self, folder_id: str | None = None, page_token: str | None = None
    ) -> tuple[list[ConnectorFile], str | None]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            payload: dict[str, Any] = {
                "filter": {"value": "page", "property": "object"},
                "page_size": 50,
            }
            if page_token:
                payload["start_cursor"] = page_token

            resp = await client.post(
                "https://api.notion.com/v1/search",
                headers=self._headers(),
                json=payload,
            )
            if resp.status_code != 200:
                logger.error("notion_search_failed", status=resp.status_code)
                return [], None

            data = resp.json()
            next_cursor = data.get("next_cursor")
            results: list[ConnectorFile] = []

            for page in data.get("results", []):
                pid = page["id"]
                props = page.get("properties", {})
                title = "Untitled Page"
                for p_val in props.values():
                    if p_val.get("type") == "title":
                        title_rt = p_val.get("title", [])
                        if title_rt:
                            title = parse_rich_text(title_rt)
                        break

                mod_time_str = page.get("last_edited_time")
                mod_time = (
                    datetime.fromisoformat(mod_time_str.replace("Z", "+00:00")) if mod_time_str else datetime.now(UTC)
                )

                results.append(
                    ConnectorFile(
                        file_id=pid,
                        name=f"{title}.md",
                        mime_type="text/markdown",
                        size_bytes=1024,
                        modified_at=mod_time,
                        source_url=page.get("url"),
                    )
                )
            return results, next_cursor

    async def fetch_changes(self, cursor: dict[str, Any]) -> tuple[list[ConnectorChange], dict[str, Any]]:
        last_synced_at = cursor.get("last_synced_at")
        async with httpx.AsyncClient(timeout=15.0) as client:
            payload: dict[str, Any] = {
                "filter": {"value": "page", "property": "object"},
                "sort": {"direction": "descending", "timestamp": "last_edited_time"},
                "page_size": 50,
            }
            resp = await client.post("https://api.notion.com/v1/search", headers=self._headers(), json=payload)
            if resp.status_code != 200:
                return [], cursor

            data = resp.json()
            new_cursor = {
                "last_synced_at": datetime.now(UTC).isoformat(),
            }

            changes: list[ConnectorChange] = []
            for page in data.get("results", []):
                mod_time_str = page.get("last_edited_time")
                if last_synced_at and mod_time_str and mod_time_str <= last_synced_at:
                    continue

                pid = page["id"]
                title = "Untitled Page"
                props = page.get("properties", {})
                for p_val in props.values():
                    if p_val.get("type") == "title":
                        title_rt = p_val.get("title", [])
                        if title_rt:
                            title = parse_rich_text(title_rt)
                        break

                mod_time = (
                    datetime.fromisoformat(mod_time_str.replace("Z", "+00:00")) if mod_time_str else datetime.now(UTC)
                )
                conn_file = ConnectorFile(
                    file_id=pid,
                    name=f"{title}.md",
                    mime_type="text/markdown",
                    size_bytes=1024,
                    modified_at=mod_time,
                    source_url=page.get("url"),
                )
                changes.append(
                    ConnectorChange(
                        file_id=pid,
                        change_type="MODIFIED",
                        file=conn_file,
                    )
                )
            return changes, new_cursor

    async def download_file(self, file_id: str) -> tuple[bytes, str]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            page_resp = await client.get(f"https://api.notion.com/v1/pages/{file_id}", headers=self._headers())
            title = f"notion_{file_id}"
            if page_resp.status_code == 200:
                p_data = page_resp.json()
                for p_val in p_data.get("properties", {}).values():
                    if p_val.get("type") == "title":
                        title_rt = p_val.get("title", [])
                        if title_rt:
                            title = parse_rich_text(title_rt)
                        break

            # Fetch page blocks recursively
            blocks_resp = await client.get(
                f"https://api.notion.com/v1/blocks/{file_id}/children",
                params={"page_size": 100},
                headers=self._headers(),
            )
            md_lines = [f"# {title}\n\n"]
            if blocks_resp.status_code == 200:
                for b in blocks_resp.json().get("results", []):
                    md_lines.append(block_to_markdown(b))

            content = "".join(md_lines).encode("utf-8")
            return content, f"{title}.md"

    async def fetch_access_control(self, file_id: str) -> list[str]:
        return []
