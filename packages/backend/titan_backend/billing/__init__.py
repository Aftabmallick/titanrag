"""Billing module — Phase 10.

Exports:
- stripe_service: Stripe Customer/Subscription/Metering management
- PLAN_CONFIG: Plan limits and CU allocations
"""

from titan_backend.billing.stripe_service import (
    PLAN_CONFIG,
    StripePlanSlug,
    create_checkout_session,
    create_customer_portal_session,
    get_or_create_stripe_customer,
    process_stripe_webhook_event,
    report_cu_usage_to_stripe,
    verify_stripe_webhook_signature,
)

__all__ = [
    "PLAN_CONFIG",
    "StripePlanSlug",
    "create_checkout_session",
    "create_customer_portal_session",
    "get_or_create_stripe_customer",
    "process_stripe_webhook_event",
    "report_cu_usage_to_stripe",
    "verify_stripe_webhook_signature",
]
