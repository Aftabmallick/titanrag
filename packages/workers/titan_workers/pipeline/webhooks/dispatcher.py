import hashlib
import hmac
import json
import time
from typing import Any

import httpx
import structlog

logger = structlog.get_logger("titanrag.webhooks")


class IngestionWebhookDispatcher:
    """
    Dispatches secure HMAC-SHA256 signed webhooks on ingestion events.
    """

    @staticmethod
    def _generate_signature(secret: str, payload_bytes: bytes, timestamp: int) -> str:
        message = f"t={timestamp}.".encode() + payload_bytes
        signature = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
        return f"t={timestamp},v1={signature}"

    @classmethod
    async def dispatch_event(
        cls,
        webhook_url: str,
        webhook_secret: str,
        event_type: str,
        document_id: str,
        workspace_id: str,
        status: str,
        chunk_count: int,
        error_message: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> bool:
        if not webhook_url:
            return False

        now = int(time.time())
        payload = {
            "event": event_type,
            "timestamp": now,
            "data": {
                "document_id": document_id,
                "workspace_id": workspace_id,
                "status": status,
                "chunk_count": chunk_count,
                "error_message": error_message,
                **(extra or {}),
            },
        }
        payload_bytes = json.dumps(payload).encode("utf-8")
        signature = cls._generate_signature(webhook_secret or "default_secret", payload_bytes, now)

        headers = {
            "Content-Type": "application/json",
            "X-TitanRAG-Signature": signature,
            "User-Agent": "TitanRAG-Webhook-Dispatcher/1.0",
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(webhook_url, content=payload_bytes, headers=headers)
                logger.info(
                    "webhook_dispatched",
                    url=webhook_url,
                    status_code=resp.status_code,
                    event=event_type,
                    document_id=document_id,
                )
                return resp.status_code < 400
        except Exception as e:
            logger.warning("webhook_dispatch_failed", url=webhook_url, error=str(e), document_id=document_id)
            return False
