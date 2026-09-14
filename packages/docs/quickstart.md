---
title: Quickstart Guide
description: Get TitanRAG running locally in under two minutes
---

# Quickstart Guide

This guide walks you through launching TitanRAG in local development using either the zero-overhead **Quickstart Profile** or the **Full Development Stack**.

## Prerequisites

Ensure you have the following installed on your host machine:
- **Docker** (version 24+ recommended with Compose V2)
- **uv** (ultra-fast Python package installer: `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Python 3.12+**
- **Node.js 20+** (if developing on the frontend)
- **Make**

---

## 1. Clone & Setup Environment

Copy the default environment variables template:

```bash
cp .env.example .env
```

Review the defaults in `.env`. By default, credentials and container network DNS hostnames are pre-configured for local Docker bridging.

---

## 2. Launch Local Environment

### Option A: Quickstart Profile (< 2 Minutes)
Spins up PostgreSQL 16 (RLS enabled), Qdrant 1.12 Vector Engine, and the FastAPI application:

```bash
make quickstart
```

This runs:
```bash
docker compose -f packages/infra/docker-compose.yml --profile quickstart up -d --wait
```

### Option B: Full Application Stack
Spins up all core services including Redis 7, Celery Workers, Outbox Relay, Celery Beat, MinIO Object Store, and LiteLLM:

```bash
make up
```

### Option C: Observability Stack (Prometheus + Grafana + Jaeger)
```bash
make obs
```

---

## 3. Run Database Migrations

Apply Alembic migrations to set up all 17 tables, composite indexes, and Row-Level Security:

```bash
make migrate
```

---

## 4. Verify System Health

Probe the deep readiness endpoint:

```bash
make health
```

Or query directly:
```bash
curl -s http://localhost:8000/health/ready | jq .
```

Expected output:
```json
{
  "status": "ready",
  "dependencies": {
    "postgres": { "status": "ok", "latency_ms": 1.2 },
    "qdrant": { "status": "ok", "latency_ms": 2.4 },
    "redis": { "status": "ok", "latency_ms": 0.8 },
    "minio": { "status": "ok", "latency_ms": 3.1 }
  }
}
```

---

## 5. Explore Interactive Documentation

- **Swagger / OpenAPI UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc UI**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Grafana Dashboards**: [http://localhost:3000](http://localhost:3000) (User: `admin` / Password: `admin`)
- **Jaeger Distributed Tracing**: [http://localhost:16686](http://localhost:16686)
- **MinIO Console**: [http://localhost:9001](http://localhost:9001) (User: `minioadmin` / Password: `minioadmin`)
