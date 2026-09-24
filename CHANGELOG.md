# TitanRAG — Changelog & Release Notes

All notable changes to the TitanRAG platform will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] — 2026-09-24 (V2.0 Enterprise Expansion Release)

### 🚀 Highlights
TitanRAG V2.0 GA brings full enterprise monetization, white-label portals, batch processing APIs, a hosted no-signup sandbox, multi-framework LLM evaluations, air-gapped security, and complete accessibility compliance.

### Added
- **Track 10.1 — Stripe Billing & CU Metering** (`8.17`):
  - Stripe Customer and Subscription synchronization (`FREE`, `PRO`, `ENTERPRISE`).
  - Compute Unit (CU) consumption aggregation and automated reporting to Stripe Billing Meters API.
  - Idempotent Stripe webhook event pipeline with database-level event deduplication.
  - Self-serve Customer Portal session creation and automated `READ_ONLY` mode on payment failure.
- **Track 10.2 — White-Label Multi-Tenant Branding** (`8.18`):
  - Per-tenant brand configuration (custom company name, primary/accent colors, logo variants, favicons).
  - Dynamic CSS custom properties injection in Next.js frontend and Shadow DOM widget.
  - Custom domain routing via CNAME and TXT challenge verification with automated SSL termination.
  - Jinja2 transactional email templating inheriting tenant branding.
- **Track 10.3 — Platform Super-Admin Panel** (`8.5`, `8.6`, `5.19`):
  - Global tenant administration with suspension controls, quota overrides, and storage breakdown.
  - Real-time system health dashboard tracking microservices, Celery queue depth, and Qdrant collections.
  - Platform-wide broadcast announcements with severity levels and automated expiry.
  - Cross-tenant audit log viewer with collapsible JSON payloads and CSV export.
- **Track 10.4 — Batch API Endpoints** (`8.20`):
  - `POST /api/v1/workspaces/{id}/batch/queries` for up to 50 concurrent questions with progress polling.
  - `POST /api/v1/workspaces/{id}/batch/uploads` for batch document ingestion (up to 100 documents).
  - `POST /api/v1/workspaces/{id}/batch/delete` for asynchronous cascade deletion (up to 500 documents).
  - Outbound HMAC-SHA256 signed webhook delivery on job completion with exponential backoff.
- **Track 10.5 — Hosted Ephemeral Sandbox** (`8.21`):
  - Public no-signup ephemeral sessions with 24-hour TTL and automated cascade cleanup.
  - Dedicated Kubernetes namespace `titanrag-sandbox` with ResourceQuotas and strict NetworkPolicies.
  - Pre-loaded golden datasets (Legal MSA, Architecture, Financial reports) for immediate demonstration.
  - Interactive 4-step guided tour modal for first-time visitors.
- **Track 10.6 — Multi-Framework Evaluation Suite** (`7.11`):
  - DeepEval integration with G-Eval coherence, contextual relevancy, and hallucination metrics.
  - Blocking CI quality gate (`scripts/ci_evaluation_gate.py`) rejecting PRs with >3% faithfulness regression.
  - 30-day quality trend sparkline charts on workspace analytics pages.
- **Track 10.7 — Log Aggregation with Loki & Promtail** (`8.5`):
  - Centralized log scraping across API, Celery workers, and databases.
  - Promtail pipeline stages redacting emails, API keys, SSNs, credit cards, and JWT tokens.
  - Grafana Log Explorer dashboard with cross-service `request_id` correlation.
- **Track 10.8 — Accessibility & i18n Finalization** (`5.26`, `5.27`):
  - WCAG 2.1 AA certified zero-violation Playwright axe-core test suite.
  - Full keyboard navigation with `Cmd+K` command palette and `?` shortcuts help overlay.
  - Arabic (RTL) and Japanese localization with dynamic `dir="rtl"` support.

---

## [1.0.0] — 2026-08-15 (V1.0 Production Core Release)

### Core Engine (Phases 1–6)
- Monorepo architecture with Docker compose and transactional outbox.
- JWT authentication, RBAC, SCIM directory synchronization, and tenant isolation via PostgreSQL RLS.
- Docling OCR parsing, batched contextual chunk prepend, and MinHash LSH deduplication.
- In-process ONNX embeddings, hybrid dense/sparse search (Qdrant + BM25), Corrective RAG (CRAG).
- Real-time Next.js chat interface with SSE streaming and PDF.js bounding-box source highlighting.
- FinOps Compute Unit (CU) ledger, RAGAS golden dataset evaluation, and Langfuse tracing.

---

## Migration Guide: V1.x to V2.0

1. **Database Schema Update**:
   Run Alembic migration `0009_phase10_billing_whitelabel` to provision the new billing, brand, batch, and sandbox tables:
   ```bash
   alembic upgrade head
   ```

2. **Environment Variables**:
   Add the following optional variables to `.env`:
   ```bash
   STRIPE_SECRET_KEY=sk_test_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   LOKI_URL=http://loki:3100
   ```
