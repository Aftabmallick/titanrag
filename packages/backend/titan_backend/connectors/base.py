import abc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ConnectorFile:
    file_id: str
    name: str
    mime_type: str
    size_bytes: int
    modified_at: datetime
    version: str = "1"
    source_url: str | None = None
    folder_path: str = "/"
    acl_permissions: list[str] = field(default_factory=list)  # list of emails/group names with read access
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectorChange:
    file_id: str
    change_type: str  # "ADDED", "MODIFIED", "DELETED"
    file: ConnectorFile | None = None  # None if DELETED


@dataclass
class SyncResult:
    connector_id: str
    status: str  # "SUCCESS", "FAILED", "PARTIAL"
    added_count: int = 0
    modified_count: int = 0
    deleted_count: int = 0
    errors: list[str] = field(default_factory=list)
    new_cursor: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


class BaseConnector(abc.ABC):
    """
    Unified abstract protocol for Enterprise SaaS connectors.
    Handles authentication, credential verification, file traversal,
    CDC delta querying, content streaming, and source ACL extraction.
    """

    def __init__(self, config: dict[str, Any], credentials: dict[str, Any]):
        self.config = config
        self.credentials = credentials

    @abc.abstractmethod
    async def test_connection(self) -> bool:
        """Validate credentials and test API connectivity with the source service."""
        pass

    @abc.abstractmethod
    async def list_files(
        self, folder_id: str | None = None, page_token: str | None = None
    ) -> tuple[list[ConnectorFile], str | None]:
        """List files in the connected workspace or specific folder."""
        pass

    @abc.abstractmethod
    async def fetch_changes(
        self, cursor: dict[str, Any]
    ) -> tuple[list[ConnectorChange], dict[str, Any]]:
        """
        Query CDC changes since the provided cursor/high-water mark.
        Returns a list of ConnectorChange items and the next state cursor.
        """
        pass

    @abc.abstractmethod
    async def download_file(self, file_id: str) -> tuple[bytes, str]:
        """
        Download raw file bytes and filename/mime_type from the source provider.
        For Google Docs/Sheets, converts to standard PDF/CSV representations.
        """
        pass

    @abc.abstractmethod
    async def fetch_access_control(self, file_id: str) -> list[str]:
        """Fetch read permission emails/identities for source ACL mirroring."""
        pass
