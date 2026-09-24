"""White-label multi-tenant branding module — Phase 10.

Exports:
- BrandMailer: Branded Jinja2 transactional email rendering
"""

from titan_backend.whitelabel.mailer import BrandMailer

__all__ = ["BrandMailer"]
