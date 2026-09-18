import json
from unittest.mock import AsyncMock, patch

import pytest
from titan_backend.collaboration.presence import PresenceManager


@pytest.mark.asyncio
async def test_presence_manager_flow():
    mock_redis = AsyncMock()
    mock_storage = {}

    async def mock_hset(key, field, val):
        mock_storage[field] = val
        return 1

    async def mock_hgetall(key):
        return mock_storage

    async def mock_hdel(key, field):
        mock_storage.pop(field, None)
        return 1

    mock_redis.hset.side_effect = mock_hset
    mock_redis.hgetall.side_effect = mock_hgetall
    mock_redis.hdel.side_effect = mock_hdel
    mock_redis.expire.return_value = True
    mock_redis.publish.return_value = 1

    with patch("titan_backend.collaboration.presence.get_redis_client", return_value=mock_redis):
        # 1. Join session
        users = await PresenceManager.user_join(
            workspace_id="ws_100",
            session_id="sess_200",
            user_id="user_alice",
            user_name="Alice",
            user_email="alice@corp.com",
        )
        assert len(users) == 1
        assert users[0]["name"] == "Alice"
        mock_redis.publish.assert_called_once()

        # 2. Heartbeat
        await PresenceManager.heartbeat("ws_100", "sess_200", "user_alice")
        mock_redis.expire.assert_called()

        # 3. Leave session
        remaining = await PresenceManager.user_leave("ws_100", "sess_200", "user_alice")
        assert len(remaining) == 0


@pytest.mark.asyncio
async def test_session_token_broadcaster():
    from titan_backend.collaboration.broadcaster import SessionTokenBroadcaster

    mock_redis = AsyncMock()
    mock_redis.publish.return_value = 1

    with patch("titan_backend.collaboration.broadcaster.get_redis_client", return_value=mock_redis):
        await SessionTokenBroadcaster.broadcast_chunk(
            session_id="sess_abc",
            event_type="token",
            data={"text": "Hello world", "token_idx": 1},
        )
        mock_redis.publish.assert_called_once()
        args, _ = mock_redis.publish.call_args
        assert args[0] == "chat_stream:sess_abc"
        payload = json.loads(args[1])
        assert payload["event"] == "token"
        assert payload["data"]["text"] == "Hello world"
