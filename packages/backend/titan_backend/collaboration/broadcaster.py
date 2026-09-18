import json
from typing import Any

import structlog
from titan_backend.clients.redis_client import get_redis_client

logger = structlog.get_logger("titanrag.collaboration.broadcaster")


class SessionTokenBroadcaster:
    """
    Broadcasts real-time streaming tokens and citation events to all active session participants.
    Backed by Redis Pub/Sub channels.
    """

    @classmethod
    async def broadcast_chunk(
        cls,
        session_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        redis = await get_redis_client()
        channel = f"chat_stream:{session_id}"
        message = {
            "event": event_type,
            "data": data,
        }
        await redis.publish(channel, json.dumps(message))
