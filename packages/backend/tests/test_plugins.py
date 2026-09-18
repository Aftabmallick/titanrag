import time
from uuid import uuid4

import httpx
import pytest
from titan_backend.db.models.plugin import HookType, Plugin
from titan_backend.services.plugins.circuit_breaker import PluginCircuitBreaker
from titan_backend.services.plugins.dispatcher import PluginDispatcher
from titan_backend.services.plugins.signer import WebhookSigner


def test_webhook_signer_generation_and_signing():
    secret = WebhookSigner.generate_secret()
    assert len(secret) == 64  # 32 bytes hex = 64 hex characters

    payload = b'{"event":"test","data":123}'
    now = int(time.time())
    sig_header, ts = WebhookSigner.sign_payload(secret, payload, timestamp=now)

    assert ts == now
    assert sig_header.startswith(f"t={now},v1=")

    # Verify signature
    assert WebhookSigner.verify_signature(
        secret=secret,
        payload_bytes=payload,
        header_value=sig_header,
        current_time=now,
    ) is True


def test_webhook_signer_tamper_detection():
    secret = WebhookSigner.generate_secret()
    payload = b'{"amount":100}'
    sig_header, now = WebhookSigner.sign_payload(secret, payload)

    # Tampered payload
    tampered = b'{"amount":1000000}'
    assert WebhookSigner.verify_signature(
        secret=secret,
        payload_bytes=tampered,
        header_value=sig_header,
        current_time=now,
    ) is False

    # Tampered secret
    other_secret = WebhookSigner.generate_secret()
    assert WebhookSigner.verify_signature(
        secret=other_secret,
        payload_bytes=payload,
        header_value=sig_header,
        current_time=now,
    ) is False


def test_webhook_signer_replay_drift_rejection():
    secret = WebhookSigner.generate_secret()
    payload = b'{"event":"replay_test"}'
    past_timestamp = int(time.time()) - 301  # 301 seconds ago (> 300s drift)

    sig_header, _ = WebhookSigner.sign_payload(secret, payload, timestamp=past_timestamp)

    # Should be rejected because drift > max_drift_seconds (300s)
    assert WebhookSigner.verify_signature(
        secret=secret,
        payload_bytes=payload,
        header_value=sig_header,
        max_drift_seconds=300,
        current_time=int(time.time()),
    ) is False

    # Within drift limit (e.g. 100 seconds ago) -> valid
    valid_past = int(time.time()) - 100
    valid_header, _ = WebhookSigner.sign_payload(secret, payload, timestamp=valid_past)
    assert WebhookSigner.verify_signature(
        secret=secret,
        payload_bytes=payload,
        header_value=valid_header,
        max_drift_seconds=300,
        current_time=int(time.time()),
    ) is True


@pytest.mark.asyncio
async def test_plugin_circuit_breaker_trip_and_cooldown():
    test_id = str(uuid4())
    await PluginCircuitBreaker.reset(test_id)

    # Initially closed: can execute
    assert await PluginCircuitBreaker.can_execute(test_id) is True

    # Record 4 failures: threshold is 5, so still can execute
    for _ in range(4):
        tripped = await PluginCircuitBreaker.record_failure(test_id)
        assert tripped is False
    assert await PluginCircuitBreaker.can_execute(test_id) is True

    # 5th failure: should trip to OPEN
    tripped = await PluginCircuitBreaker.record_failure(test_id)
    assert tripped is True

    # Now circuit is open: execution blocked
    assert await PluginCircuitBreaker.can_execute(test_id) is False

    # Reset circuit
    await PluginCircuitBreaker.record_success(test_id)
    assert await PluginCircuitBreaker.can_execute(test_id) is True


@pytest.mark.asyncio
async def test_plugin_dispatcher_with_mock_transport():
    secret = WebhookSigner.generate_secret()
    plugin = Plugin(
        tenant_id=uuid4(),
        workspace_id=uuid4(),
        name="Contract Enriched Parser",
        slug="contract-parser",
        endpoint_url="https://external-service.test/webhook",
        webhook_secret=secret,
        hooks=["ON_PARSE"],
        timeout_ms=1000,
        is_active=True,
    )

    received_headers = {}

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal received_headers
        received_headers = dict(request.headers)
        # Verify incoming signature using WebhookSigner
        sig_header = request.headers.get("X-Titan-Signature", "")
        verified = WebhookSigner.verify_signature(
            secret=secret,
            payload_bytes=request.content,
            header_value=sig_header,
        )
        if not verified:
            return httpx.Response(401, json={"error": "Signature verification failed"})
        return httpx.Response(200, json={"parsed": True, "clauses": ["indemnity"]})

    mock_transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=mock_transport) as client:
        # Note: db can be None here because we are testing dispatcher logic in isolation
        dispatcher = PluginDispatcher(db=None, http_client=client)  # type: ignore
        res = await dispatcher.dispatch_single(
            plugin=plugin,
            hook_type=HookType.ON_PARSE,
            payload={"filename": "agreement.pdf", "text": "Confidential terms"},
        )

    assert res.success is True
    assert res.status_code == 200
    assert res.data["parsed"] is True
    assert res.data["clauses"] == ["indemnity"]
    assert "x-titan-signature" in received_headers
    assert received_headers.get("x-titan-hook") == "ON_PARSE"
