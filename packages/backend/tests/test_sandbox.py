"""Unit tests for Hosted Sandbox Environment — Phase 10."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from titan_backend.db.models.billing import SandboxSession


def test_sandbox_session_lifecycle():
    """Verify ephemeral sandbox session invariants."""
    tenant_id = uuid4()
    workspace_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)
    expiry = now + timedelta(hours=24)

    session = SandboxSession(
        ephemeral_tenant_id=tenant_id,
        ephemeral_workspace_id=workspace_id,
        ephemeral_user_id=user_id,
        access_token_hash="hash_abc123",
        client_ip="192.168.1.100",
        client_fingerprint="fp_browser_hash",
        expires_at=expiry,
        is_purged=False,
        query_count=0,
        upload_count=0,
        storage_bytes=0,
        tour_step=0,
    )

    assert session.is_purged is False
    assert session.tour_step == 0
    assert session.expires_at > now
    assert session.client_ip == "192.168.1.100"

    # Simulate usage
    session.query_count += 1
    session.tour_step = 2
    assert session.query_count == 1
    assert session.tour_step == 2


def test_sandbox_purge_eligibility():
    """Sessions with expired timestamp should be flagged for purge."""
    expired_time = datetime.now(UTC) - timedelta(hours=1)
    future_time = datetime.now(UTC) + timedelta(hours=20)

    expired_session = SandboxSession(
        ephemeral_tenant_id=uuid4(),
        ephemeral_workspace_id=uuid4(),
        ephemeral_user_id=uuid4(),
        access_token_hash="hash1",
        client_ip="10.0.0.1",
        expires_at=expired_time,
        is_purged=False,
    )

    active_session = SandboxSession(
        ephemeral_tenant_id=uuid4(),
        ephemeral_workspace_id=uuid4(),
        ephemeral_user_id=uuid4(),
        access_token_hash="hash2",
        client_ip="10.0.0.2",
        expires_at=future_time,
        is_purged=False,
    )

    now = datetime.now(UTC)
    assert expired_session.expires_at < now
    assert active_session.expires_at > now
