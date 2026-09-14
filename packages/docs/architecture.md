---
title: System Architecture
description: Comprehensive technical architecture of the TitanRAG Enterprise Platform
---

# System Architecture

TitanRAG is engineered from the ground up as a zero-leakage, multi-tenant multimodal retrieval-augmented generation engine with dual-write safety and distributed observability.

## High-Level Topology

```
┌──────────────────────────────────────────────────────────────┐
│                    Next.js 14 Frontend                       │
└──────────────────────────────┬───────────────────────────────┘
                               │ HTTP / SSE / Streaming
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                    FastAPI Core Engine                       │
│  - SecurityHeaders & Correlation ID (structlog contextvars)  │
│  - In-Process ONNX Fast-Path Routing (<15ms)                 │
│  - SQLAlchemy 2.0 Async Session Management                   │
│  - OpenTelemetry Tracing Exporter                            │
└──────────────┬──────────────────────────────┬────────────────┘
               │                              │
       Writes  ▼                      Reads   ▼
┌──────────────────────────────┐   ┌──────────────────────────────┐
│        PostgreSQL 16         │   │          Qdrant 1.12         │
│  - Tenant RLS Enforcement    │   │  - INT8 Scalar Quantization  │
│  - `chunk_outbox` Table      │   │  - Multi-tenant Payload Idx  │
│  - Documents & Chunks Ledger │   │  - Cosine Dense Vectors      │
└──────────────┬───────────────┘   └──────────────▲───────────────┘
               │                                  │
               │ Tails `chunk_outbox`             │ Upserts Vectors
               │ (SKIP LOCKED)                    │
               ▼                                  │
┌──────────────────────────────┐                  │
│     Outbox Relay Process     ├──────────────────┘
└──────────────────────────────┘
               │
               ▼ Coordinates
┌──────────────────────────────────────────────────────────────┐
│                  Celery Task Infrastructure                  │
│  - Broker: Redis 7 (appendonly yes, noeviction)              │
│  - Worker Bounds: --max-memory-per-child=1GB RAM             │
│  - Core Queue: p0_interactive, p1_default, p2_bulk_sync      │
│  - Heavy ML Queue: heavy_ml, reranking                       │
│  - Beat Scheduler: Daily Vector Reconciler, Housekeeping     │
└──────────────────────────────────────────────────────────────┘
```

## Architectural Pillars

### 1. The Transactional Outbox Pattern
Direct synchronous writes from an API endpoint to both PostgreSQL and an external vector database (like Qdrant) suffer from the dual-write problem: if the vector database times out after Postgres commits, data is permanently desynchronized.

In TitanRAG:
1. All chunk creations and updates write to `chunks` and `chunk_outbox` inside an **atomic PostgreSQL transaction**.
2. An asynchronous **Outbox Relay** process tails `chunk_outbox` using `SELECT ... FOR UPDATE SKIP LOCKED`.
3. The relay pushes vector upserts to Qdrant with exponential backoff and idempotent retry tracking.
4. On success, the record is marked `PROCESSED`. On repeated failure, it transitions to `FAILED` for dead-letter triage.

### 2. Multi-Tenant Isolation & Defense-in-Depth
- **Database Level**: PostgreSQL Row-Level Security (`ENABLE ROW LEVEL SECURITY`) with `SET LOCAL app.tenant_id` session variables.
- **Application Level**: Every query generator appends explicit `WHERE tenant_id = :tenant_id` clauses to prevent session bleeding under connection poolers like PgBouncer.
- **Vector Level**: Every Qdrant collection query includes mandatory payload filter:
  ```json
  "must": [{ "key": "tenant_id", "match": { "value": "<tenant_id>" } }]
  ```
- **Storage Level**: S3 object paths partitioned strictly as `/{tenant_id}/{workspace_id}/{document_id}/...`.

### 3. Decoupled Worker Tiers & Memory Bounds
Heavy ML frameworks (PyTorch, Docling, Presidio, ColPali) often suffer from subtle native C++ memory leaks. TitanRAG strictly splits Celery into two distinct container tiers:
- **`celery-core`**: High-concurrency I/O, chunking, outbox publishing.
- **`celery-heavy-ml`**: GPU/OCR/vision workers with `--max-memory-per-child=1048576` (1GB RAM) to automatically recycle worker children after large batches.
