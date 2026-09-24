"""Webhook Handler & Dispatcher — Phase 10.

Provides:
- Inbound Stripe webhook verification and idempotency handling
- Outbound signed webhook dispatcher for asynchronous Batch API jobs and alerting
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.billing.stripe_service import (
    process_stripe_webhook_event,
    verify_stripe_webhook_signature,
)

logger = structlog.get_logger(__name__)


class StripeWebhookProcessor:
    """Processes incoming Stripe webhooks safely and idempotently."""

    def __init__(self, db: AsyncSession, webhook_secret: str) -> None:
        self.db = db
        self.webhook_secret = webhook_secret

    async def handle_inbound_webhook(
        self,
        raw_body: bytes,
        signature_header: str,
    ) -> dict[str, Any]:
        """Verify signature and dispatch event to database-backed idempotent handler."""
        if not verify_stripe_webhook_signature(raw_body, signature_header, self.webhook_secret):
            logger.warning("stripe_webhook_invalid_signature")
            return {"status": "error", "message": "Invalid webhook signature"}

        try:
            event_payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            return {"status": "error", "message": "Malformed JSON payload"}

        stripe_event_id = event_payload.get("id")
        event_type = event_payload.get("type")
        customer_id = event_payload.get("data", {}).get("object", {}).get("customer")

        if not stripe_event_id or not event_type:
            return {"status": "error", "message": "Missing required event fields"}

        processed = await process_stripe_webhook_event(
            db=self.db,
            stripe_event_id=stripe_event_id,
            event_type=event_type,
            stripe_customer_id=customer_id,
            payload=event_payload,
        )

        return {
            "status": "success",
            "event_id": stripe_event_id,
            "processed": processed,
        }


class OutboundWebhookDispatcher:
    """Dispatches outbound HTTP webhooks signed with HMAC-SHA256 for batch jobs / events."""

    @staticmethod
    def sign_payload(secret: str, payload_bytes: bytes) -> str:
        """Calculate HMAC-SHA256 hex digest for outbound payload."""
        return hmac.new(
            secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

    @classmethod
    async def deliver_webhook(
        cls,
        target_url: str,
        secret: str,
        payload: dict[str, Any],
        max_retries: int = 3,
        timeout_seconds: float = 10.0,
    ) -> bool:
        """Deliver webhook with exponential backoff retry on failure."""
        payload_bytes = json.dumps(payload).encode("utf-8")
        timestamp = str(int(time.time()))
        signature = cls.sign_payload(secret, f"{timestamp}.".encode() + payload_bytes)

        headers = {
            "Content-Type": "application/json",
            "X-Titan-Signature": f"t={timestamp},v1={signature}",
            "User-Agent": "TitanRAG-Webhook-Delivery/2.0",
        }

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            for attempt in range(1, max_retries + 1):
                try:
                    resp = await client.post(target_url, content=payload_bytes, headers=headers)
                    if 200 <= resp.status_code < 300:
                        logger.info(
                            "outbound_webhook_delivered",
                            target_url=target_url,
                            attempt=attempt,
                            status_code=resp.status_code,
                        )
                        return True
                    logger.warning(
                        "outbound_webhook_non_2xx",
                        target_url=target_url,
                        attempt=attempt,
                        status_code=resp.status_code,
                    )
                except Exception as exc:
                    logger.warning(
                        "outbound_webhook_delivery_error",
                        target_url=target_url,
                        attempt=attempt,
                        error=str(exc),
                    )

                if attempt < max_retries:
                    import asyncio

                    await asyncio.sleep(2**attempt)

        return False
