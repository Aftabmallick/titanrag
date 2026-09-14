import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse

from titan_backend.clients.redis_client import get_redis_client
from titan_backend.core.dependencies import CurrentUser, get_current_user
from titan_backend.core.logging import logger

router = APIRouter(prefix="/events", tags=["System Events"])

SYSTEM_EVENTS_CHANNEL = "titanrag:system_events"
SYSTEM_EVENTS_HISTORY_KEY = "titanrag:events:history"


async def broadcast_event(event_type: str, payload: dict[str, Any], tenant_id: str | None = None) -> None:
    """Broadcasts a system event to Redis Pub/Sub and appends to tenant event history buffer."""
    event_id = str(uuid.uuid4())
    message = {
        "id": event_id,
        "type": event_type,
        "tenant_id": str(tenant_id) if tenant_id else "*",
        "payload": payload,
    }
    msg_json = json.dumps(message)
    try:
        redis: Any = await get_redis_client()
        # 1. Publish to live pub/sub channel
        await redis.publish(SYSTEM_EVENTS_CHANNEL, msg_json)

        # 2. Append to tenant event buffer (capped at 1,000 events)
        buffer_key = f"{SYSTEM_EVENTS_HISTORY_KEY}:{tenant_id or 'global'}"
        await redis.rpush(buffer_key, msg_json)
        await redis.ltrim(buffer_key, -1000, -1)
        await redis.expire(buffer_key, 86400 * 7)

        logger.debug("system_event_broadcasted", event_type=event_type, event_id=event_id)
    except Exception as e:
        logger.warning("broadcast_event_failed", error=str(e), event_type=event_type)


@router.get("", response_class=StreamingResponse)
async def subscribe_to_events(
    request: Request,
    types: str | None = Query(default=None, description="Comma-separated event types to filter"),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    current_user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    """Real-time SSE event bus streaming system events with Last-Event-ID event replay."""
    allowed_types = set(t.strip() for t in types.split(",")) if types else None

    async def event_generator() -> AsyncGenerator[str, None]:
        redis: Any = await get_redis_client()
        pubsub = redis.pubsub()
        await pubsub.subscribe(SYSTEM_EVENTS_CHANNEL)

        try:
            # Yield initial connection event
            yield f"event: connected\ndata: {json.dumps({'message': 'Connected to TitanRAG event stream', 'user_id': str(current_user.user_id)})}\n\n"

            # Replay missed events if Last-Event-ID was provided
            if last_event_id:
                try:
                    tenant_history_key = f"{SYSTEM_EVENTS_HISTORY_KEY}:{current_user.tenant_id}"
                    global_history_key = f"{SYSTEM_EVENTS_HISTORY_KEY}:global"
                    history_items = await redis.lrange(tenant_history_key, 0, -1) or []
                    global_items = await redis.lrange(global_history_key, 0, -1) or []
                    all_history = [json.loads(item) for item in (history_items + global_items)]

                    # Find where Last-Event-ID occurred
                    target_idx = None
                    for i, ev in enumerate(all_history):
                        if ev.get("id") == last_event_id:
                            target_idx = i
                            break

                    replay_events = all_history[target_idx + 1 :] if target_idx is not None else all_history[-50:]
                    for ev in replay_events:
                        ev_type = ev.get("type")
                        if allowed_types and ev_type not in allowed_types:
                            continue
                        ev_id = ev.get("id", "")
                        yield f"id: {ev_id}\nevent: {ev_type}\ndata: {json.dumps(ev.get('payload', {}))}\n\n"
                    logger.info("events_replayed", count=len(replay_events), last_event_id=last_event_id)
                except Exception as e:
                    logger.warning("event_replay_failed", error=str(e))

            # Live event stream
            while True:
                if await request.is_disconnected():
                    logger.info("event_stream_client_disconnected", user_id=str(current_user.user_id))
                    break

                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("type") == "message":
                    raw_data = msg.get("data")
                    if raw_data:
                        event_obj = json.loads(raw_data)
                        ev_tenant = event_obj.get("tenant_id")
                        ev_type = event_obj.get("type")

                        # Scope to current tenant
                        if ev_tenant not in ("*", str(current_user.tenant_id)):
                            continue

                        # Filter by requested event types
                        if allowed_types and ev_type not in allowed_types:
                            continue

                        ev_id = event_obj.get("id", str(uuid.uuid4()))
                        yield f"id: {ev_id}\nevent: {ev_type}\ndata: {json.dumps(event_obj.get('payload', {}))}\n\n"

                await asyncio.sleep(0.1)
        finally:
            await pubsub.unsubscribe(SYSTEM_EVENTS_CHANNEL)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
