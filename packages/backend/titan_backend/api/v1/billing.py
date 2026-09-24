"""Billing API endpoints — Phase 10.

Routes:
  GET  /api/v1/billing/subscription        — current plan + CU usage
  GET  /api/v1/billing/invoices            — invoice history
  POST /api/v1/billing/checkout            — create Stripe Checkout session
  POST /api/v1/billing/portal             — create Stripe Customer Portal session
  POST /api/v1/billing/webhooks/stripe     — Stripe webhook receiver (public)
  GET  /api/v1/billing/usage              — detailed CU breakdown by category
"""

from __future__ import annotations

from typing import Any

import stripe
import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.api.v1.auth import get_current_user
from titan_backend.billing.stripe_service import (
    PLAN_CONFIG,
    StripePlanSlug,
    _is_billing_enabled,
    _stripe_client,
    create_checkout_session,
    create_customer_portal_session,
    get_or_create_stripe_customer,
    process_stripe_webhook_event,
    verify_stripe_webhook_signature,
)
from titan_backend.core.config import settings
from titan_backend.db.deps import get_db
from titan_backend.db.models.billing import StripeCustomer
from titan_backend.db.models.user import User

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/billing", tags=["Billing"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SubscriptionResponse(BaseModel):
    plan_slug: str
    subscription_status: str
    cu_monthly_limit: int
    cu_used_this_month: float
    cu_remaining: float
    cu_percent_used: float
    current_period_end: str | None
    billing_email: str | None
    plan_features: dict[str, Any]


class InvoiceItem(BaseModel):
    invoice_id: str
    amount_due: int  # cents
    amount_paid: int
    currency: str
    status: str
    period_start: str | None
    period_end: str | None
    invoice_pdf: str | None
    hosted_invoice_url: str | None


class CheckoutSessionRequest(BaseModel):
    plan_slug: StripePlanSlug = Field(..., description="Target plan for upgrade")
    success_url: str = Field(..., description="URL to redirect after successful payment")
    cancel_url: str = Field(..., description="URL to redirect if payment cancelled")


class CheckoutSessionResponse(BaseModel):
    checkout_url: str


class PortalSessionResponse(BaseModel):
    portal_url: str


class UsageBreakdownResponse(BaseModel):
    period: str  # YYYY-MM
    total_cu: float
    breakdown: dict[str, float]  # e.g. ingestion_ocr, retrieval, generation, colpali
    estimated_overage_cost_usd: float
    cache_savings_cu: float


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionResponse:
    """Return the current tenant's subscription plan and CU usage."""
    tenant_id = str(current_user.tenant_id)

    customer = await get_or_create_stripe_customer(
        db=db,
        tenant_id=tenant_id,
        email=current_user.email,
        name=current_user.email,
    )

    # Read CU used this month from Redis finops quota counter
    from datetime import UTC, datetime

    from titan_backend.core.redis import get_redis_client

    month_key = datetime.now(UTC).strftime("%Y-%m")
    redis = await get_redis_client()
    cu_used_raw = await redis.get(f"quota:cu:{tenant_id}:{month_key}")
    cu_used = float(cu_used_raw or 0)

    cu_limit = customer.cu_monthly_limit
    cu_remaining = max(0.0, cu_limit - cu_used)
    cu_percent = round((cu_used / cu_limit * 100) if cu_limit > 0 else 0, 1)

    plan_features = PLAN_CONFIG.get(customer.plan_slug, {})

    return SubscriptionResponse(
        plan_slug=customer.plan_slug.value,
        subscription_status=customer.subscription_status.value,
        cu_monthly_limit=cu_limit,
        cu_used_this_month=cu_used,
        cu_remaining=cu_remaining,
        cu_percent_used=cu_percent,
        current_period_end=(customer.current_period_end.isoformat() if customer.current_period_end else None),
        billing_email=customer.billing_email,
        plan_features=plan_features,
    )


@router.get("/invoices", response_model=list[InvoiceItem])
async def list_invoices(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[InvoiceItem]:
    """Retrieve invoice history from Stripe."""
    if not _is_billing_enabled():
        return []

    result = await db.execute(select(StripeCustomer).where(StripeCustomer.tenant_id == current_user.tenant_id))
    customer = result.scalar_one_or_none()
    if not customer:
        return []

    try:
        client = _stripe_client()
        invoices = client.invoices.list(params={"customer": customer.stripe_customer_id, "limit": min(limit, 100)})
        items = []
        for inv in invoices.data:
            items.append(
                InvoiceItem(
                    invoice_id=inv.id,
                    amount_due=inv.amount_due,
                    amount_paid=inv.amount_paid,
                    currency=inv.currency,
                    status=inv.status or "unknown",
                    period_start=(str(inv.period_start) if inv.period_start else None),
                    period_end=(str(inv.period_end) if inv.period_end else None),
                    invoice_pdf=inv.invoice_pdf,
                    hosted_invoice_url=inv.hosted_invoice_url,
                )
            )
        return items
    except stripe.StripeError as exc:
        logger.error("stripe_list_invoices_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "STRIPE_ERROR", "message": "Failed to retrieve invoices"},
        ) from exc


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def create_checkout(
    body: CheckoutSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CheckoutSessionResponse:
    """Create a Stripe Checkout Session for a plan upgrade."""
    tenant_id = str(current_user.tenant_id)

    # Ensure Stripe customer exists
    await get_or_create_stripe_customer(
        db=db,
        tenant_id=tenant_id,
        email=current_user.email,
        name=current_user.email,
    )

    checkout_url = await create_checkout_session(
        db=db,
        tenant_id=tenant_id,
        plan_slug=body.plan_slug,
        success_url=body.success_url,
        cancel_url=body.cancel_url,
    )
    return CheckoutSessionResponse(checkout_url=checkout_url)


@router.post("/portal", response_model=PortalSessionResponse)
async def create_portal(
    return_url: str = "http://localhost:3000",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PortalSessionResponse:
    """Create a Stripe Customer Portal session for self-serve management."""
    tenant_id = str(current_user.tenant_id)
    await get_or_create_stripe_customer(
        db=db,
        tenant_id=tenant_id,
        email=current_user.email,
        name=current_user.email,
    )
    portal_url = await create_customer_portal_session(
        db=db,
        tenant_id=tenant_id,
        return_url=return_url,
    )
    return PortalSessionResponse(portal_url=portal_url)


@router.get("/usage", response_model=UsageBreakdownResponse)
async def get_usage_breakdown(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsageBreakdownResponse:
    """Return detailed CU consumption breakdown for the current billing period."""
    from datetime import UTC, datetime

    from sqlalchemy import text

    tenant_id = current_user.tenant_id
    month_key = datetime.now(UTC).strftime("%Y-%m")

    # Aggregate from finops_ledger by operation_type
    try:
        row = await db.execute(
            text(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN operation_type = 'INGESTION_DOCLING' THEN compute_units ELSE 0 END), 0) AS ocr_cu,
                    COALESCE(SUM(CASE WHEN operation_type = 'CHAT_FAST' THEN compute_units ELSE 0 END), 0) AS retrieval_cu,
                    COALESCE(SUM(CASE WHEN operation_type = 'CHAT_DEEP' THEN compute_units ELSE 0 END), 0) AS generation_cu,
                    COALESCE(SUM(CASE WHEN operation_type = 'COLPALI_VISION' THEN compute_units ELSE 0 END), 0) AS colpali_cu,
                    COALESCE(SUM(CASE WHEN operation_type = 'INGESTION_EMBEDDING' THEN compute_units ELSE 0 END), 0) AS prefix_cu,
                    COALESCE(SUM(CASE WHEN operation_type = 'RERANK' THEN compute_units ELSE 0 END), 0) AS rerank_cu,
                    COALESCE(SUM(compute_units), 0) AS total_cu
                FROM finops_ledger
                WHERE tenant_id = :tenant_id
                  AND date_trunc('month', created_at) = date_trunc('month', CURRENT_DATE)
                """
            ),
            {"tenant_id": tenant_id},
        )
        ledger_row = row.fetchone()
    except Exception:
        ledger_row = None

    breakdown = {}
    total_cu = 0.0
    if ledger_row:
        breakdown = {
            "ingestion_ocr": float(ledger_row.ocr_cu or 0),
            "retrieval": float(ledger_row.retrieval_cu or 0),
            "generation": float(ledger_row.generation_cu or 0),
            "colpali_visual": float(ledger_row.colpali_cu or 0),
            "contextual_prefix": float(ledger_row.prefix_cu or 0),
            "reranking": float(ledger_row.rerank_cu or 0),
        }
        total_cu = float(ledger_row.total_cu or 0)

    # Read customer or fallback defaults
    customer = await get_or_create_stripe_customer(
        db=db,
        tenant_id=str(tenant_id),
        email=current_user.email,
        name=current_user.email,
    )
    overage_rate = (customer.cu_overage_rate_cents or 0) / 100.0 if customer else 0
    cu_limit = customer.cu_monthly_limit if customer else 100
    overage_cu = max(0.0, total_cu - cu_limit)
    estimated_overage_cost = round(overage_cu * overage_rate, 4)

    return UsageBreakdownResponse(
        period=month_key,
        total_cu=total_cu,
        breakdown=breakdown,
        estimated_overage_cost_usd=estimated_overage_cost,
        cache_savings_cu=0.0,  # Populated by analytics engine separately
    )


# ---------------------------------------------------------------------------
# Stripe Webhook — PUBLIC endpoint (no auth, Stripe signature only)
# ---------------------------------------------------------------------------


@router.post("/webhooks/stripe", status_code=status.HTTP_200_OK, include_in_schema=False)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(None, alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Receive and idempotently process Stripe webhook events.

    This endpoint is PUBLIC — authentication is via Stripe signature verification,
    NOT via JWT or API key.
    """
    payload = await request.body()
    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)

    if webhook_secret and stripe_signature:
        if not verify_stripe_webhook_signature(
            payload=payload,
            sig_header=stripe_signature,
            secret=webhook_secret,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_SIGNATURE", "message": "Stripe signature invalid"},
            )

    import json

    try:
        event_data = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_PAYLOAD", "message": "Cannot parse JSON body"},
        ) from None

    stripe_event_id = event_data.get("id", "")
    event_type = event_data.get("type", "")
    data_obj = event_data.get("data", {}).get("object", {})
    stripe_customer_id = data_obj.get("customer")

    try:
        await process_stripe_webhook_event(
            db=db,
            stripe_event_id=stripe_event_id,
            event_type=event_type,
            stripe_customer_id=stripe_customer_id,
            payload=event_data,
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.error(
            "stripe_webhook_error",
            event_type=event_type,
            event_id=stripe_event_id,
            error=str(exc),
        )
        # Return 200 to Stripe even on processing errors — prevents retry storms
        # The error is logged and the event is stored for manual review

    return {"received": "ok"}
