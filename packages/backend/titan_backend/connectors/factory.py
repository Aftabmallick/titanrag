from typing import Any

from titan_backend.connectors.base import BaseConnector
from titan_backend.connectors.confluence import ConfluenceConnector
from titan_backend.connectors.google_drive import GoogleDriveConnector
from titan_backend.connectors.notion import NotionConnector
from titan_backend.connectors.sharepoint import SharePointConnector


def get_connector(connector_type: str, config: dict[str, Any], credentials: dict[str, Any]) -> BaseConnector:
    """Factory returning the appropriate enterprise connector instance."""
    ctype = connector_type.lower().strip()
    if ctype in ("gdrive", "google_drive"):
        return GoogleDriveConnector(config, credentials)
    elif ctype in ("sharepoint", "onedrive"):
        return SharePointConnector(config, credentials)
    elif ctype == "confluence":
        return ConfluenceConnector(config, credentials)
    elif ctype == "notion":
        return NotionConnector(config, credentials)
    else:
        raise ValueError(f"Unsupported connector type: '{connector_type}'")


class ConnectorFactory:
    """Factory helper class for creating enterprise SaaS connectors."""

    @staticmethod
    def create_connector(
        connector_type: str, credentials: dict[str, Any], config: dict[str, Any] | None = None
    ) -> BaseConnector:
        return get_connector(connector_type, config or {}, credentials)
