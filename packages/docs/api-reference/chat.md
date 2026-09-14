---
title: Chat & RAG Streaming API
description: Real-time SSE streaming query generation with grounded citations
---

# Chat & RAG Streaming API

The Chat API provides high-throughput conversational search, fast-path intent routing, hybrid vector retrieval, and server-sent events (SSE) streaming answers with page-level visual bounding-box citations.

## Retrieval Strategies

1. **Fast-Path In-Process Routing (<15ms)**:
   - Direct matching for greetings, simple lookups, or cached queries.
2. **Hybrid Search (Dense + Sparse)**:
   - Dense: 1536-dim cosine search on Qdrant.
   - Sparse / BM25: Keyword recurrence scoring.
   - Reciprocal Rank Fusion (RRF) with configurable alpha weights.
3. **Cross-Encoder Reranking**:
   - High-precision reranking on top 20 candidate chunks down to top 5.

## Endpoints (Phase 4 Spec)

- `POST /api/v1/workspaces/{workspace_id}/chat/sessions`: Create new conversation session.
- `GET /api/v1/workspaces/{workspace_id}/chat/sessions`: List active chat history.
- `POST /api/v1/workspaces/{workspace_id}/chat/query`: Submit query and receive streaming SSE tokens:
  ```text
  event: metadata
  data: {"session_id": "...", "citations": [{"chunk_id": "...", "page": 4}]}

  event: token
  data: {"delta": "According to the annual report..."}

  event: done
  data: {"tokens_used": 342, "latency_ms": 420.5}
  ```
