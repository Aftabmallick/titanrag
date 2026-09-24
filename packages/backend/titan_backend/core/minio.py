"""MinIO compatibility module forwarding to titan_backend.clients.s3_client."""

from minio import Minio

from titan_backend.clients.s3_client import (
    build_scoped_storage_path,
    check_minio_health,
    get_minio_client,
)

get_minio_client_sync = get_minio_client

__all__ = [
    "Minio",
    "build_scoped_storage_path",
    "check_minio_health",
    "get_minio_client",
    "get_minio_client_sync",
]
