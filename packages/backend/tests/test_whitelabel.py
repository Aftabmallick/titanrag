"""Unit tests for White-Label Multi-Tenant Branding — Phase 10."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from titan_backend.db.models.billing import TenantBrandConfig
from titan_backend.whitelabel.mailer import BrandMailer


@pytest.mark.asyncio
async def test_brand_config_defaults():
    """Verify brand configuration defaults and properties."""
    tenant_id = uuid4()
    config = TenantBrandConfig(
        tenant_id=tenant_id,
        company_name="Acme AI",
        primary_color="#10b981",
        accent_color="#3b82f6",
        custom_domain="ai.acme.corp",
        domain_verified=False,
        domain_verification_token="verify_token_12345",
    )

    assert config.company_name == "Acme AI"
    assert config.primary_color == "#10b981"
    assert config.accent_color == "#3b82f6"
    assert config.custom_domain == "ai.acme.corp"
    assert config.domain_verified is False


@pytest.mark.asyncio
async def test_brand_mailer_render_with_custom_branding():
    """Mailer should merge tenant branding into HTML email templates."""
    session = AsyncMock()
    tenant_id = uuid4()

    mock_config = TenantBrandConfig(
        tenant_id=tenant_id,
        company_name="Wayne Enterprises",
        primary_color="#1e293b",
        accent_color="#f59e0b",
        from_email="noreply@wayne.com",
        from_name="Wayne Tech",
    )
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_config
    session.execute.return_value = mock_res

    mailer = BrandMailer(session)
    html, brand_ctx = await mailer.render_template(
        tenant_id=tenant_id,
        template_name="invite.html.j2",
        context={
            "recipient_name": "Bruce Wayne",
            "inviter_name": "Alfred",
            "invite_url": "https://wayne.titanrag.ai/accept?token=xyz",
        },
    )

    assert "Wayne Enterprises" in html
    assert "#1e293b" in html
    assert "Bruce Wayne" in html
    assert "Alfred" in html
    assert brand_ctx["company_name"] == "Wayne Enterprises"
    assert brand_ctx["from_email"] == "noreply@wayne.com"


@pytest.mark.asyncio
async def test_brand_mailer_fallback_defaults():
    """When no tenant brand config exists, mailer falls back to TitanRAG defaults."""
    session = AsyncMock()
    tenant_id = uuid4()

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_res

    mailer = BrandMailer(session)
    brand_ctx = await mailer.get_brand_context(tenant_id)

    assert brand_ctx["company_name"] == "TitanRAG"
    assert brand_ctx["primary_color"] == "#6366f1"
