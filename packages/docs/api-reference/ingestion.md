---
title: Ingestion & Document Pipeline
description: Specifications and endpoints for asynchronous document parsing and vector indexing
---

# Ingestion & Documents API

The Ingestion Pipeline handles asynchronous multimodal document parsing, chunking, contextual enrichment, and vector embedding projections through the Transactional Outbox.

## Supported Document Formats

- PDF (`application/pdf`)
- Office Documents (`.docx`, `.pptx`, `.xlsx`)
- Plain Text & Markdown (`text/plain`, `text/markdown`)
- HTML & Web Pages (`text/html`)

## Ingestion Flow Stages

```
1. UPLOAD       -> MinIO Storage Object Path
2. PARSING      -> Docling / OCR text & table extraction
3. CHUNKING     -> Recursive character or semantic sectioning
4. ENRICHMENT   -> Contextual parent-child chunk linking
5. EMBEDDING    -> Dense vector generation
6. OUTBOX       -> Transactional chunk_outbox insertion
7. PROJECTION   -> Qdrant HNSW indexing via Outbox Relay
```

## Endpoints (Phase 3 Spec)

- `POST /api/v1/workspaces/{workspace_id}/documents/upload`: Multi-part form document upload.
- `GET /api/v1/workspaces/{workspace_id}/documents`: List workspace documents with pagination and status filters.
- `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}`: Document detail with versions and metadata.
- `GET /api/v1/workspaces/{workspace_id}/ingestion/{task_id}`: Real-time SSE or polled task progress.
- `DELETE /api/v1/workspaces/{workspace_id}/documents/{document_id}`: Soft delete document and emit tombstone outbox event.
