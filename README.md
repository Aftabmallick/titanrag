# TitanRAG Enterprise

Enterprise-Grade Multi-Tenant Multimodal RAG Engine with PostgreSQL Row-Level Security, Transactional Outbox vector projections, decoupled stateless Celery worker tiers, in-process ONNX Fast-Path routing, and complete OpenTelemetry/Prometheus observability.

---

## Repository Structure

```
titanrag/
├── Makefile                                # Monorepo developer orchestrator
├── pyproject.toml                          # uv workspace root + ruff/mypy/pytest configs
├── .env.defaults                           # Default container networking configuration
├── .env.example                            # Local developer host overrides
├── .github/workflows/                      # GitHub Actions CI matrix
├── packages/
│   ├── backend/                            # FastAPI Core REST, SSE & Outbox Publisher
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── alembic.ini
│   │   ├── alembic/versions/               # Database DDL & RLS migrations
│   │   └── titan_backend/                  # Core application package
│   ├── workers/                            # Decoupled Celery Workers & Outbox Relay
│   │   ├── Dockerfile.core                 # Lightweight I/O, Outbox Relay
│   │   ├── Dockerfile.heavy                # Deep OCR, ColPali, Heavy ML
│   │   ├── pyproject.toml
│   │   └── titan_workers/                  # Async queues & outbox poller
│   ├── frontend/                           # Next.js 14+ App Router Client
│   │   ├── Dockerfile
│   │   ├── package.json
│   │   └── src/app/                        # Next.js App Router
│   └── infra/                              # Docker Compose orchestration & Observability
│       ├── docker-compose.yml              # Multi-profile compose stack (14+ services)
│       ├── litellm/config.yaml             # Multi-provider LLM gateway configuration
│       ├── prometheus/prometheus.yml       # Metrics scraping config
│       └── grafana/                        # Pre-provisioned datasources & dashboards
```

---

## Quickstart Guide

### 1. Zero-Config Docker Quickstart (< 2 minutes)
Spins up lightweight PostgreSQL 16 (with RLS enabled), Qdrant vector engine, and FastAPI backend:
```bash
make quickstart
```

Check health:
```bash
make health
```

### 2. Full Development Stack
Spins up core services (PostgreSQL, Redis, Qdrant, MinIO, LiteLLM, FastAPI, Celery, Outbox Relay):
```bash
make up
```

With Observability (Prometheus, Grafana, Jaeger):
```bash
make full
```

### 3. Local Python Development (Host)
Install virtual environment and dependencies using `uv`:
```bash
uv sync --all-packages
uv add --dev pytest pytest-asyncio ruff mypy
```

Run test suite:
```bash
make test
```

Run linter & formatting check:
```bash
make lint
```
