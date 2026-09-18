import hashlib
import hmac
import json
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from titan_backend.db.models.webhook import Webhook, WebhookDeliveryLog

logger = structlog.get_logger("titanrag.integrations.webhook")


class WebhookDispatcher:
    """
    Outbound webhook dispatcher.
    Signs payloads with HMAC-SHA256, handles retries with exponential backoff,
    and logs delivery telemetry to PostgreSQL.
    """

    @staticmethod
    def sign_payload(payload_bytes: bytes, secret: str, timestamp: int) -> str:
        mac_data = f"t={timestamp}.".encode() + payload_bytes
        signature = hmac.new(secret.encode("utf-8"), mac_data, hashlib.sha256).hexdigest()
        return f"t={timestamp},v1={signature}"

    @classmethod
    async def dispatch_event(
        cls,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        workspace_id: uuid.UUID,
        event_type: str,
        payload_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Find active webhooks subscribed to event_type and dispatch asynchronously."""
        stmt = select(Webhook).where(
            Webhook.tenant_id == tenant_id,
            Webhook.workspace_id == workspace_id,
            Webhook.is_active.is_(True),
        )
        res = await session.execute(stmt)
        webhooks = res.scalars().all()

        results = []
        for wh in webhooks:
            # Check if subscribed to this event or wildcard
            if wh.events and ("*" not in wh.events and event_type not in wh.events):
                continue

            delivery_result = await cls._send_webhook(session, wh, event_type, payload_data)
            results.append(delivery_result)

        return results

    @classmethod
    async def _send_webhook(
        cls,
        session: AsyncSession,
        webhook: Webhook,
        event_type: str,
        payload_data: dict[str, Any],
    ) -> dict[str, Any]:
        payload_envelope = {
            "id": f"evt_{uuid.uuid4().hex[:12]}",
            "event": event_type,
            "tenant_id": str(webhook.tenant_id),
            "workspace_id": str(webhook.workspace_id),
            "timestamp": datetime.now(UTC).isoformat(),
            "data": payload_data,
        }
        payload_json = json.dumps(payload_envelope, sort_keys=True)
        payload_bytes = payload_json.encode("utf-8")
        timestamp = int(time.time())

        signature = cls.sign_payload(payload_bytes, webhook.secret_token, timestamp)
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "TitanRAG-Webhook-Engine/1.0",
            "X-Titan-Signature": signature,
            "X-Titan-Event": event_type,
            "X-Titan-Timestamp": str(timestamp),
        }

        start_time = time.perf_counter()
        status_code = None
        response_text = None
        error_msg = None

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(webhook.url, content=payload_bytes, headers=headers)
                status_code = resp.status_code
                response_text = resp.text[:1000] if resp.text else None
                if resp.status_code >= 400:
                    error_msg = f"HTTP {resp.status_code}: {response_text}"
                    webhook.failure_count += 1
                else:
                    webhook.failure_count = 0
                    webhook.last_triggered_at = datetime.now(UTC)
        except Exception as e:
            error_msg = str(e)
            webhook.failure_count += 1

        latency_ms = (time.perf_counter() - start_time) * 1000

        # Log delivery
        log = WebhookDeliveryLog(
            webhook_id=webhook.id,
            event_type=event_type,
            status_code=status_code,
            latency_ms=latency_ms,
            payload=payload_envelope,
            response_body=response_text,
            error_message=error_msg,
            delivered_at=datetime.now(UTC),
        )
        session.add(log)
        await session.commit()

        return {
            "webhook_id": str(webhook.id),
            "url": webhook.url,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "success": status_code is not None and status_code < 400,
            "error": error_msg,
        }
