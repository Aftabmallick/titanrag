from datetime import datetime, timezone
from typing import Any
import httpx
import structlog

from titan_backend.connectors.base import BaseConnector, ConnectorChange, ConnectorFile

logger = structlog.get_logger("titanrag.connectors.gdrive")

GOOGLE_EXPORT_MIME_TYPES = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": ("text/csv", ".csv"),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
}


class GoogleDriveConnector(BaseConnector):
    """
    Enterprise Google Drive Connector with OAuth2 refresh,
    CDC changes.list tracking, Google Workspace export, and permission mirroring.
    """

    def __init__(self, config: dict[str, Any], credentials: dict[str, Any]):
        super().__init__(config, credentials)
        self.access_token = self.credentials.get("access_token", "")
        self.refresh_token = self.credentials.get("refresh_token", "")
        self.client_id = self.credentials.get("client_id", "")
        self.client_secret = self.credentials.get("client_secret", "")
        self.folder_id = self.config.get("folder_id")

    async def _refresh_access_token_if_needed(self, client: httpx.AsyncClient) -> str:
        if self.access_token and not self.refresh_token:
            return self.access_token

        if not self.refresh_token:
            return self.access_token

        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }
        try:
            resp = await client.post(token_url, data=payload)
            if resp.status_code == 200:
                data = resp.json()
                self.access_token = data.get("access_token", self.access_token)
        except Exception as e:
            logger.warning("gdrive_token_refresh_failed", error=str(e))
        return self.access_token

    async def test_connection(self) -> bool:
        if not self.access_token and not self.refresh_token:
            return False
        async with httpx.AsyncClient(timeout=10.0) as client:
            token = await self._refresh_access_token_if_needed(client)
            headers = {"Authorization": f"Bearer {token}"}
            try:
                resp = await client.get(
                    "https://www.googleapis.com/drive/v3/about",
                    params={"fields": "user,storageQuota"},
                    headers=headers,
                )
                return resp.status_code == 200
            except Exception as e:
                logger.warning("gdrive_test_connection_error", error=str(e))
                return False

    async def list_files(
        self, folder_id: str | None = None, page_token: str | None = None
    ) -> tuple[list[ConnectorFile], str | None]:
        target_folder = folder_id or self.folder_id
        q_parts = ["trashed = false"]
        if target_folder:
            q_parts.append(f"'{target_folder}' in parents")
        q = " and ".join(q_parts)

        async with httpx.AsyncClient(timeout=15.0) as client:
            token = await self._refresh_access_token_if_needed(client)
            headers = {"Authorization": f"Bearer {token}"}
            params: dict[str, Any] = {
                "q": q,
                "pageSize": 100,
                "fields": "nextPageToken, files(id, name, mimeType, size, modifiedTime, webViewLink, permissions)",
            }
            if page_token:
                params["pageToken"] = page_token

            resp = await client.get(
                "https://www.googleapis.com/drive/v3/files",
                params=params,
                headers=headers,
            )
            if resp.status_code != 200:
                logger.error("gdrive_list_files_failed", status=resp.status_code, body=resp.text)
                return [], None

            data = resp.json()
            next_page = data.get("nextPageToken")
            results: list[ConnectorFile] = []

            for f in data.get("files", []):
                # skip raw folders in the file listing
                if f.get("mimeType") == "application/vnd.google-apps.folder":
                    continue

                mod_time_str = f.get("modifiedTime")
                mod_time = (
                    datetime.fromisoformat(mod_time_str.replace("Z", "+00:00"))
                    if mod_time_str
                    else datetime.now(timezone.utc)
                )

                acl_permissions = [
                    p.get("emailAddress")
                    for p in f.get("permissions", [])
                    if p.get("emailAddress")
                ]

                results.append(
                    ConnectorFile(
                        file_id=f["id"],
                        name=f["name"],
                        mime_type=f.get("mimeType", "application/octet-stream"),
                        size_bytes=int(f.get("size", 0)),
                        modified_at=mod_time,
                        source_url=f.get("webViewLink"),
                        acl_permissions=acl_permissions,
                    )
                )
            return results, next_page

    async def fetch_changes(
        self, cursor: dict[str, Any]
    ) -> tuple[list[ConnectorChange], dict[str, Any]]:
        start_page_token = cursor.get("page_token")
        async with httpx.AsyncClient(timeout=15.0) as client:
            token = await self._refresh_access_token_if_needed(client)
            headers = {"Authorization": f"Bearer {token}"}

            if not start_page_token:
                # First run: acquire initial start token
                resp = await client.get(
                    "https://www.googleapis.com/drive/v3/changes/startPageToken",
                    headers=headers,
                )
                if resp.status_code == 200:
                    start_page_token = resp.json().get("startPageToken")
                else:
                    return [], {"page_token": start_page_token}

            changes_resp = await client.get(
                "https://www.googleapis.com/drive/v3/changes",
                params={
                    "pageToken": start_page_token,
                    "fields": "nextPageToken, newStartPageToken, changes(fileId, removed, file(id, name, mimeType, size, modifiedTime, webViewLink, permissions))",
                },
                headers=headers,
            )
            if changes_resp.status_code != 200:
                logger.error("gdrive_changes_failed", status=changes_resp.status_code)
                return [], {"page_token": start_page_token}

            data = changes_resp.json()
            new_cursor = {
                "page_token": data.get("newStartPageToken") or data.get("nextPageToken", start_page_token),
                "synced_at": datetime.now(timezone.utc).isoformat(),
            }

            changes: list[ConnectorChange] = []
            for item in data.get("changes", []):
                file_id = item.get("fileId")
                if not file_id:
                    continue

                if item.get("removed", False):
                    changes.append(ConnectorChange(file_id=file_id, change_type="DELETED"))
                else:
                    f = item.get("file", {})
                    if f.get("mimeType") == "application/vnd.google-apps.folder":
                        continue

                    mod_time_str = f.get("modifiedTime")
                    mod_time = (
                        datetime.fromisoformat(mod_time_str.replace("Z", "+00:00"))
                        if mod_time_str
                        else datetime.now(timezone.utc)
                    )
                    acl_perms = [
                        p.get("emailAddress")
                        for p in f.get("permissions", [])
                        if p.get("emailAddress")
                    ]
                    conn_file = ConnectorFile(
                        file_id=file_id,
                        name=f.get("name", f"file_{file_id}"),
                        mime_type=f.get("mimeType", "application/octet-stream"),
                        size_bytes=int(f.get("size", 0)),
                        modified_at=mod_time,
                        source_url=f.get("webViewLink"),
                        acl_permissions=acl_perms,
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
            token = await self._refresh_access_token_if_needed(client)
            headers = {"Authorization": f"Bearer {token}"}

            meta_resp = await client.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                params={"fields": "name, mimeType"},
                headers=headers,
            )
            name = f"file_{file_id}"
            mime_type = "application/octet-stream"
            if meta_resp.status_code == 200:
                meta = meta_resp.json()
                name = meta.get("name", name)
                mime_type = meta.get("mimeType", mime_type)

            if mime_type in GOOGLE_EXPORT_MIME_TYPES:
                export_mime, ext = GOOGLE_EXPORT_MIME_TYPES[mime_type]
                export_resp = await client.get(
                    f"https://www.googleapis.com/drive/v3/files/{file_id}/export",
                    params={"mimeType": export_mime},
                    headers=headers,
                )
                if not name.endswith(ext):
                    name += ext
                return export_resp.content, name

            dl_resp = await client.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                params={"alt": "media"},
                headers=headers,
            )
            return dl_resp.content, name

    async def fetch_access_control(self, file_id: str) -> list[str]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            token = await self._refresh_access_token_if_needed(client)
            headers = {"Authorization": f"Bearer {token}"}
            resp = await client.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}/permissions",
                params={"fields": "permissions(emailAddress, role)"},
                headers=headers,
            )
            if resp.status_code != 200:
                return []
            perms = resp.json().get("permissions", [])
            return [p["emailAddress"] for p in perms if p.get("emailAddress")]
