from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest

from titan_backend.connectors.base import ConnectorChange, ConnectorFile
from titan_backend.connectors.cdc_manager import CdcDeltaSyncManager
from titan_backend.connectors.confluence import ConfluenceConnector, html_to_markdown
from titan_backend.connectors.factory import get_connector
from titan_backend.connectors.google_drive import GoogleDriveConnector
from titan_backend.connectors.notion import NotionConnector, block_to_markdown
from titan_backend.connectors.sharepoint import SharePointConnector
from titan_backend.db.models.connectors import Connector, ConnectorStatus, SyncStatus


def test_confluence_html_to_markdown():
    html = "<h1>Project Title</h1><p>Welcome to <b>TitanRAG</b>.</p><ul><li>Item 1</li><li>Item 2</li></ul>"
    md = html_to_markdown(html)
    assert "# Project Title" in md
    assert "Welcome to TitanRAG." in md
    assert "* Item 1" in md
    assert "* Item 2" in md


def test_notion_block_to_markdown():
    block_h1 = {
        "type": "heading_1",
        "heading_1": {"rich_text": [{"plain_text": "Notion Header", "annotations": {}}]},
    }
    block_callout = {
        "type": "callout",
        "callout": {"rich_text": [{"plain_text": "Important notice", "annotations": {"bold": True}}]},
    }
    block_code = {
        "type": "code",
        "code": {"language": "python", "rich_text": [{"plain_text": "x = 42", "annotations": {}}]},
    }

    assert block_to_markdown(block_h1) == "# Notion Header\n\n"
    assert "> [!NOTE]" in block_to_markdown(block_callout)
    assert "**Important notice**" in block_to_markdown(block_callout)
    assert "```python\nx = 42\n```\n\n" == block_to_markdown(block_code)


def test_connector_factory():
    gdrive = get_connector("gdrive", {"folder_id": "root"}, {"access_token": "token"})
    assert isinstance(gdrive, GoogleDriveConnector)

    sp = get_connector("sharepoint", {"site_id": "site1"}, {"access_token": "token"})
    assert isinstance(sp, SharePointConnector)

    conf = get_connector("confluence", {"base_url": "https://wiki.corp.com"}, {"api_token": "tok"})
    assert isinstance(conf, ConfluenceConnector)

    notion = get_connector("notion", {}, {"api_key": "secret"})
    assert isinstance(notion, NotionConnector)

    with pytest.raises(ValueError):
        get_connector("invalid_crm", {}, {})


@pytest.mark.asyncio
async def test_google_drive_fetch_changes_mock():
    connector = GoogleDriveConnector(
        config={"folder_id": "folder_123"},
        credentials={"access_token": "mock_token"},
    )

    mock_resp_changes = {
        "newStartPageToken": "token_v2",
        "changes": [
            {
                "fileId": "file_1",
                "removed": False,
                "file": {
                    "id": "file_1",
                    "name": "DesignDoc.pdf",
                    "mimeType": "application/pdf",
                    "size": "1048576",
                    "modifiedTime": "2026-09-18T12:00:00Z",
                    "permissions": [{"emailAddress": "alice@corp.com"}],
                },
            },
            {
                "fileId": "file_2",
                "removed": True,
            },
        ],
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_resp_changes
        mock_get.return_value = mock_response

        changes, next_cursor = await connector.fetch_changes({"page_token": "token_v1"})
        assert len(changes) == 2
        assert changes[0].change_type == "MODIFIED"
        assert changes[0].file.name == "DesignDoc.pdf"
        assert changes[0].file.acl_permissions == ["alice@corp.com"]
        assert changes[1].change_type == "DELETED"
        assert changes[1].file_id == "file_2"
        assert next_cursor["page_token"] == "token_v2"


@pytest.mark.asyncio
async def test_sharepoint_fetch_changes_mock():
    connector = SharePointConnector(
        config={"site_id": "site_abc"},
        credentials={"access_token": "mock_token"},
    )

    mock_resp = {
        "@odata.deltaLink": "https://graph.microsoft.com/delta_v2",
        "value": [
            {
                "id": "item_1",
                "name": "Report.docx",
                "lastModifiedDateTime": "2026-09-18T10:00:00Z",
                "file": {"mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
                "size": 2048,
            },
            {
                "id": "item_2",
                "deleted": {"state": "deleted"},
            },
        ],
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_resp
        mock_get.return_value = mock_response

        changes, next_cursor = await connector.fetch_changes({})
        assert len(changes) == 2
        assert changes[0].change_type == "MODIFIED"
        assert changes[0].file.name == "Report.docx"
        assert changes[1].change_type == "DELETED"
        assert next_cursor["delta_link"] == "https://graph.microsoft.com/delta_v2"


@pytest.mark.asyncio
async def test_cdc_sync_manager_execution():
    mock_session = AsyncMock()
    connector_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    mock_connector = Connector(
        id=connector_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        name="Corp GDrive",
        connector_type="gdrive",
        status=ConnectorStatus.ACTIVE,
        config={},
        auth_credentials={"access_token": "valid_token"},
        cdc_cursor={},
        sync_stats={},
    )

    async def mock_execute(stmt):
        mock_res = MagicMock()
        # If querying Connector
        if "FROM connectors" in str(stmt) or "connectors." in str(stmt):
            mock_res.scalar_one_or_none.return_value = mock_connector
        else:
            mock_res.scalar_one_or_none.return_value = None
            mock_res.scalars.return_value.all.return_value = []
        return mock_res

    mock_session.execute.side_effect = mock_execute

    manager = CdcDeltaSyncManager(mock_session)

    mock_changes = [
        ConnectorChange(
            file_id="ext_doc_1",
            change_type="MODIFIED",
            file=ConnectorFile(
                file_id="ext_doc_1",
                name="SecurityPolicy.pdf",
                mime_type="application/pdf",
                size_bytes=1000,
                modified_at=datetime.now(timezone.utc),
                acl_permissions=["secops@corp.com"],
            ),
        ),
        ConnectorChange(
            file_id="ext_doc_2",
            change_type="DELETED",
            file=None,
        ),
    ]

    with patch("titan_backend.connectors.google_drive.GoogleDriveConnector.fetch_changes", new_callable=AsyncMock) as mock_fetch, \
         patch("titan_backend.connectors.google_drive.GoogleDriveConnector.download_file", new_callable=AsyncMock) as mock_dl, \
         patch.object(manager.minio_client, "put_object") as mock_put, \
         patch.object(manager.qdrant_client, "delete", new_callable=AsyncMock) as mock_qdelete:

        mock_fetch.return_value = (mock_changes, {"page_token": "cursor_v2"})
        mock_dl.return_value = (b"%PDF-1.4 Mock Content", "SecurityPolicy.pdf")

        sync_res = await manager.sync_connector(connector_id)

        assert sync_res.status == "SUCCESS"
        assert sync_res.added_count == 1
        assert sync_res.deleted_count == 1
        assert sync_res.new_cursor == {"page_token": "cursor_v2"}
        mock_put.assert_called_once()
        mock_qdelete.assert_not_called()  # No existing doc found in mock DB search
