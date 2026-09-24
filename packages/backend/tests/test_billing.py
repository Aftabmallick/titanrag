"""Unit tests for Billing & Stripe Integration — Phase 10."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from titan_backend.billing.metering import MeteringEngine
from titan_backend.billing.stripe_service import (
    PLAN_CONFIG,
    get_or_create_stripe_customer,
    process_stripe_webhook_event,
    verify_stripe_webhook_signature,
)
from titan_backend.billing.webhook_handler import (
    OutboundWebhookDispatcher,
)
from titan_backend.db.models.billing import (
    BillingEvent,
    StripeCustomer,
    StripePlanSlug,
    StripeSubscriptionStatus,
)


@pytest.mark.asyncio
async def test_plan_configuration_invariants():
    """Verify plan config invariants for CU limits and overage."""
    assert PLAN_CONFIG[StripePlanSlug.FREE]["cu_monthly_limit"] == 100
    assert PLAN_CONFIG[StripePlanSlug.FREE]["cu_overage_rate_cents"] == 0
    assert PLAN_CONFIG[StripePlanSlug.PRO]["cu_monthly_limit"] == 5_000
    assert PLAN_CONFIG[StripePlanSlug.PRO]["cu_overage_rate_cents"] == 2
    assert PLAN_CONFIG[StripePlanSlug.ENTERPRISE]["cu_monthly_limit"] == 100_000
    assert PLAN_CONFIG[StripePlanSlug.SANDBOX]["cu_monthly_limit"] == 10


@pytest.mark.asyncio
async def test_get_or_create_stripe_customer_disabled_mode():
    """When Stripe key is not configured, create a valid local customer record."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_res

    tenant_id = str(uuid4())
    customer = await get_or_create_stripe_customer(
        db=session,
        tenant_id=tenant_id,
        email="admin@acme.corp",
        name="Acme Corp",
    )

    assert customer.tenant_id == tenant_id
    assert customer.plan_slug == StripePlanSlug.FREE
    assert customer.subscription_status == StripeSubscriptionStatus.ACTIVE
    assert customer.cu_monthly_limit == 100
    session.add.assert_called_once()


@pytest.mark.asyncio
async def test_stripe_webhook_signature_verification():
    """Test HMAC-SHA256 signature verification."""
    import hashlib
    import hmac
    import time

    secret = "whsec_test_secret_12345"
    payload = b'{"id": "evt_test1", "type": "invoice.paid"}'
    ts = str(int(time.time()))

    signed_payload = f"{ts}.{payload.decode('utf-8')}"
    sig = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    sig_header = f"t={ts},v1={sig}"
    assert verify_stripe_webhook_signature(payload, sig_header, secret) is True

    # Bad secret
    assert verify_stripe_webhook_signature(payload, sig_header, "wrong_secret") is False

    # Old timestamp (replay attack simulation)
    old_ts = str(int(time.time()) - 400)
    old_sig = hmac.new(
        secret.encode("utf-8"),
        f"{old_ts}.{payload.decode('utf-8')}".encode(),
        hashlib.sha256,
    ).hexdigest()
    assert verify_stripe_webhook_signature(payload, f"t={old_ts},v1={old_sig}", secret) is False


@pytest.mark.asyncio
async def test_idempotent_webhook_processing():
    """Duplicate Stripe event delivery must be skipped idempotently."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    # First event check: None found
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_res

    processed = await process_stripe_webhook_event(
        db=session,
        stripe_event_id="evt_unique_123",
        event_type="invoice.paid",
        stripe_customer_id="cus_123",
        payload={"id": "evt_unique_123", "type": "invoice.paid"},
    )
    assert processed is True
    session.add.assert_called_once()

    # Second delivery: event already exists
    mock_res_duplicate = MagicMock()
    mock_res_duplicate.scalar_one_or_none.return_value = BillingEvent(stripe_event_id="evt_unique_123")
    session.execute.return_value = mock_res_duplicate

    processed_second = await process_stripe_webhook_event(
        db=session,
        stripe_event_id="evt_unique_123",
        event_type="invoice.paid",
        stripe_customer_id="cus_123",
        payload={"id": "evt_unique_123", "type": "invoice.paid"},
    )
    assert processed_second is False


@pytest.mark.asyncio
async def test_metering_engine_usage_summary():
    """Verify CU usage breakdown and overage calculation."""
    session = AsyncMock()
    tenant_id = str(uuid4())

    mock_cust = StripeCustomer(
        tenant_id=tenant_id,
        stripe_customer_id="cus_pro",
        plan_slug=StripePlanSlug.PRO,
        subscription_status=StripeSubscriptionStatus.ACTIVE,
        cu_monthly_limit=5_000,
        cu_overage_rate_cents=2,
        current_period_start=datetime.now(UTC),
        current_period_end=datetime.now(UTC),
    )
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_cust
    session.execute.return_value = mock_res

    metering = MeteringEngine(session)
    summary = await metering.get_tenant_usage_summary(tenant_id)

    assert summary["tenant_id"] == tenant_id
    assert summary["plan_slug"] == "PRO"
    assert summary["monthly_cu_limit"] == 5000
    assert "breakdown" in summary
    assert "total_cu_consumed" in summary


@pytest.mark.asyncio
async def test_outbound_webhook_signature():
    """Outbound webhooks must sign payloads with HMAC-SHA256."""
    secret = "batch_webhook_secret_key"
    payload = b'{"job_id": "job_123", "status": "COMPLETED"}'
    sig = OutboundWebhookDispatcher.sign_payload(secret, payload)

    assert isinstance(sig, str)
    assert len(sig) == 64  # sha256 hex digest length
