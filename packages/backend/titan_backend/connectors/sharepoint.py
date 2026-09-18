from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from titan_backend.connectors.base import BaseConnector, ConnectorChange, ConnectorFile

logger = structlog.get_logger("titanrag.connectors.sharepoint")


class SharePointConnector(BaseConnector):
    """
    Microsoft SharePoint and OneDrive connector using Microsoft Graph API v1.0.
    Implements delta query CDC synchronization and enterprise ACL permission mirroring.
    """

    def __init__(self, config: dict[str, Any], credentials: dict[str, Any]):
        super().__init__(config, credentials)
        self.tenant_id_azure = self.credentials.get("azure_tenant_id", "")
        self.client_id = self.credentials.get("client_id", "")
        self.client_secret = self.credentials.get("client_secret", "")
        self.access_token = self.credentials.get("access_token", "")
        self.site_id = self.config.get("site_id", "")
        self.drive_id = self.config.get("drive_id", "")

    async def _get_access_token(self, client: httpx.AsyncClient) -> str:
        if self.access_token:
            return str(self.access_token)

        if not (self.tenant_id_azure and self.client_id and self.client_secret):
            return ""

        url = f"https://login.microsoftonline.com/{self.tenant_id_azure}/oauth2/v2.0/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }
        try:
            resp = await client.post(url, data=data)
            if resp.status_code == 200:
                self.access_token = str(resp.json().get("access_token", ""))
        except Exception as e:
            logger.error("sharepoint_token_request_error", error=str(e))
        return str(self.access_token)

    def _get_base_drive_url(self) -> str:
        if self.drive_id:
            return f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}"
        if self.site_id:
            return f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drive"
        return "https://graph.microsoft.com/v1.0/me/drive"

    async def test_connection(self) -> bool:
        async with httpx.AsyncClient(timeout=10.0) as client:
            token = await self._get_access_token(client)
            if not token:
                return False
            headers = {"Authorization": f"Bearer {token}"}
            try:
                resp = await client.get(self._get_base_drive_url(), headers=headers)
                return resp.status_code == 200
            except Exception as e:
                logger.warning("sharepoint_test_connection_error", error=str(e))
                return False

    async def list_files(
        self, folder_id: str | None = None, page_token: str | None = None
    ) -> tuple[list[ConnectorFile], str | None]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token = await self._get_access_token(client)
            headers = {"Authorization": f"Bearer {token}"}

            if page_token:
                url = page_token
            elif folder_id:
                url = f"{self._get_base_drive_url()}/items/{folder_id}/children"
            else:
                url = f"{self._get_base_drive_url()}/root/children"

            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.error("sharepoint_list_files_failed", status=resp.status_code)
                return [], None

            data = resp.json()
            next_link = data.get("@odata.nextLink")
            results: list[ConnectorFile] = []

            for item in data.get("value", []):
                # Skip folders
                if "folder" in item:
                    continue

                mod_time_str = item.get("lastModifiedDateTime")
                mod_time = (
                    datetime.fromisoformat(mod_time_str.replace("Z", "+00:00")) if mod_time_str else datetime.now(UTC)
                )

                results.append(
                    ConnectorFile(
                        file_id=item["id"],
                        name=item["name"],
                        mime_type=item.get("file", {}).get("mimeType", "application/octet-stream"),
                        size_bytes=int(item.get("size", 0)),
                        modified_at=mod_time,
                        source_url=item.get("webUrl"),
                        acl_permissions=[],
                    )
                )
            return results, next_link

    async def fetch_changes(self, cursor: dict[str, Any]) -> tuple[list[ConnectorChange], dict[str, Any]]:
        delta_link = cursor.get("delta_link")
        async with httpx.AsyncClient(timeout=20.0) as client:
            token = await self._get_access_token(client)
            headers = {"Authorization": f"Bearer {token}"}

            url = delta_link or f"{self._get_base_drive_url()}/root/delta"
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.error("sharepoint_delta_query_failed", status=resp.status_code)
                return [], cursor

            data = resp.json()
            new_delta_link = data.get("@odata.deltaLink") or data.get("@odata.nextLink", url)
            new_cursor = {
                "delta_link": new_delta_link,
                "synced_at": datetime.now(UTC).isoformat(),
            }

            changes: list[ConnectorChange] = []
            for item in data.get("value", []):
                file_id = item.get("id")
                if not file_id:
                    continue

                if "deleted" in item:
                    changes.append(ConnectorChange(file_id=file_id, change_type="DELETED"))
                elif "file" in item:
                    mod_time_str = item.get("lastModifiedDateTime")
                    mod_time = (
                        datetime.fromisoformat(mod_time_str.replace("Z", "+00:00"))
                        if mod_time_str
                        else datetime.now(UTC)
                    )
                    conn_file = ConnectorFile(
                        file_id=file_id,
                        name=item.get("name", f"file_{file_id}"),
                        mime_type=item.get("file", {}).get("mimeType", "application/octet-stream"),
                        size_bytes=int(item.get("size", 0)),
                        modified_at=mod_time,
                        source_url=item.get("webUrl"),
                        acl_permissions=[],
                    )
                    changes.append(
                        ConnectorChange(
                            file_id=file_id,
                            change_type="MODIFIED",
                            file=conn_file,
                        )
                    )
            return changes, new_cursor

    async def download_file(self, file_id: str) -> tuple[bytes, str]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await self._get_access_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            meta_resp = await client.get(
                f"{self._get_base_drive_url()}/items/{file_id}",
                headers=headers,
            )
            name = f"file_{file_id}"
            if meta_resp.status_code == 200:
                name = meta_resp.json().get("name", name)

            content_resp = await client.get(
                f"{self._get_base_drive_url()}/items/{file_id}/content",
                headers=headers,
                follow_redirects=True,
            )
            return content_resp.content, name

    async def fetch_access_control(self, file_id: str) -> list[str]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            token = await self._get_access_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            resp = await client.get(
                f"{self._get_base_drive_url()}/items/{file_id}/permissions",
                headers=headers,
            )
            if resp.status_code != 200:
                return []
            perms = resp.json().get("value", [])
            acl_users: list[str] = []
            for p in perms:
                user_email = p.get("grantedToV2", {}).get("user", {}).get("email") or p.get("grantedTo", {}).get(
                    "user", {}
                ).get("email")
                if user_email:
                    acl_users.append(user_email)
            return acl_users
