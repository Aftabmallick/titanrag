import structlog
from minio import Minio

from titan_backend.core.config import settings

logger = structlog.get_logger("titanrag.s3")

_minio_client: Minio | None = None


def get_minio_client() -> Minio:
    global _minio_client
    if _minio_client is None:
        _minio_client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ROOT_USER,
            secret_key=settings.MINIO_ROOT_PASSWORD,
            secure=settings.MINIO_USE_SSL,
        )
    return _minio_client


async def check_minio_health() -> bool:
    try:
        client = get_minio_client()
        # list buckets to verify connectivity
        client.list_buckets()
        return True
    except Exception as e:
        logger.warning("minio_health_check_failed", error=str(e))
        return False
