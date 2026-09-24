"""DB dependencies re-export."""

from titan_backend.db.session import get_db

__all__ = ["get_db"]
