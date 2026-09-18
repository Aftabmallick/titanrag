from datetime import datetime, timezone
import json
from typing import Any
import structlog

from titan_backend.clients.redis_client import get_redis_client

logger = structlog.get_logger("titanrag.collaboration.presence")


class PresenceManager:
    """
    Redis-backed real-time multi-user presence and active session tracking.
    """

    TTL_SECONDS = 60

    @classmethod
    def _presence_key(cls, workspace_id: str, session_id: str) -> str:
        return f"presence:{workspace_id}:{session_id}"

    @classmethod
    async def user_join(
        cls,
        workspace_id: str,
        session_id: str,
        user_id: str,
        user_name: str,
        user_email: str,
    ) -> list[dict[str, Any]]:
        redis = await get_redis_client()
        key = cls._presence_key(workspace_id, session_id)
        user_info = {
            "user_id": user_id,
            "name": user_name,
            "email": user_email,
            "joined_at": datetime.now(timezone.utc).isoformat(),
        }
        await redis.hset(key, user_id, json.dumps(user_info))
        await redis.expire(key, cls.TTL_SECONDS)

        # Broadcast event
        evt = {"event": "join", "session_id": session_id, "user": user_info}
        await redis.publish(f"presence_events:{workspace_id}", json.dumps(evt))

        return await cls.get_active_users(workspace_id, session_id)

    @classmethod
    async def user_leave(
        cls,
        workspace_id: str,
        session_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        redis = await get_redis_client()
        key = cls._presence_key(workspace_id, session_id)
        await redis.hdel(key, user_id)

        evt = {"event": "leave", "session_id": session_id, "user_id": user_id}
        await redis.publish(f"presence_events:{workspace_id}", json.dumps(evt))

        return await cls.get_active_users(workspace_id, session_id)

    @classmethod
    async def heartbeat(
        cls,
        workspace_id: str,
        session_id: str,
        user_id: str,
    ) -> None:
        redis = await get_redis_client()
        key = cls._presence_key(workspace_id, session_id)
        await redis.expire(key, cls.TTL_SECONDS)

    @classmethod
    async def get_active_users(
        cls,
        workspace_id: str,
        session_id: str,
    ) -> list[dict[str, Any]]:
        redis = await get_redis_client()
        key = cls._presence_key(workspace_id, session_id)
        raw_users = await redis.hgetall(key)
        users = []
        for v in raw_users.values():
            try:
                users.append(json.loads(v))
            except Exception:
                pass
        return users
