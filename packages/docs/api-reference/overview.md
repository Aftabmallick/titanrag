---
title: API Overview
description: Overview of the TitanRAG REST API conventions, headers, and error handling
---

# API Overview

All TitanRAG endpoints are versioned under `/api/v1` and return strict JSON payloads conforming to enterprise contracts.

## Base URL

- **Development**: `http://localhost:8000/api/v1`
- **Interactive OpenAPI**: `http://localhost:8000/docs`

## Standard Request Headers

| Header | Description | Required |
| :--- | :--- | :---: |
| `Authorization` | Bearer token (`Bearer <jwt_token>`) | Yes (Protected routes) |
| `X-API-Key` | API Key authentication (`rg_...`) | Alternative to Bearer |
| `X-Request-ID` | Unique request correlation ID (UUIDv4) | Optional (Generated if omitted) |
| `Content-Type` | `application/json` | Yes (for JSON bodies) |

## Standard Error Response Contract

All non-2xx responses adhere to the standard error model:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "The requested resource was not found",
    "details": {},
    "request_id": "7f7dfa4e-128b-4bfe-995a-675cf39f88d7"
  }
}
```

### Common Error Codes

- `BAD_REQUEST` (400): Malformed JSON or input validation failure.
- `UNAUTHORIZED` (401): Missing or expired token / API key.
- `FORBIDDEN` (403): Role or ACL group lacks permission.
- `NOT_FOUND` (404): Resource does not exist or belongs to another tenant.
- `CONFLICT` (409): Unique constraint violation (e.g., duplicate email/key).
- `SERVICE_UNAVAILABLE` (503): Downstream database or storage degraded.
