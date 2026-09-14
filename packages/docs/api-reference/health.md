---
title: Health & Probes API
description: Liveness and deep readiness probes for Kubernetes and load balancers
---

# Health & Readiness Probes

TitanRAG exposes deep health inspection endpoints to support container orchestration platforms and zero-downtime rolling updates.

---

## 1. Liveness Probe

Checks if the FastAPI server process is alive and accepting connections.

- **Endpoint**: `GET /health/live`
- **Authentication**: None
- **Response Code**: `200 OK`

### Response
```json
{
  "status": "alive"
}
```

---

## 2. Readiness Probe

Actively executes short-timeout network checks against all downstream dependencies (PostgreSQL, Qdrant, Redis, MinIO) and measures round-trip latency in milliseconds.

- **Endpoint**: `GET /health/ready`
- **Authentication**: None
- **Response Codes**:
  - `200 OK`: All mandatory dependencies are healthy.
  - `503 Service Unavailable`: One or more dependencies failed or timed out.

### Response (Healthy)
```json
{
  "status": "ready",
  "dependencies": {
    "postgres": {
      "status": "ok",
      "latency_ms": 1.45,
      "error": null
    },
    "qdrant": {
      "status": "ok",
      "latency_ms": 2.18,
      "error": null
    },
    "redis": {
      "status": "ok",
      "latency_ms": 0.85,
      "error": null
    },
    "minio": {
      "status": "ok",
      "latency_ms": 3.12,
      "error": null
    }
  }
}
```

---

## 3. Prometheus Metrics

Returns standard Prometheus-formatted metrics scraped by Prometheus server.

- **Endpoint**: `GET /metrics`
- **Content-Type**: `text/plain; version=0.0.4; charset=utf-8`

### Sample Metrics
```text
# HELP http_requests_total Total HTTP Requests
# TYPE http_requests_total counter
http_requests_total{handler="/health/live",method="GET",status="200"} 124.0

# HELP http_request_duration_seconds HTTP Request Latency in seconds
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{handler="/health/live",le="0.01",method="GET"} 120.0
```
