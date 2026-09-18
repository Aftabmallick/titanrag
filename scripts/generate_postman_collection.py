"""Generate exportable Postman/Insomnia Collection for TitanRAG API v1."""

import json
from pathlib import Path
from uuid import uuid4

POSTMAN_COLLECTION = {
    "info": {
        "_postman_id": str(uuid4()),
        "name": "TitanRAG Enterprise API v1",
        "description": "Production Postman collection for TitanRAG multi-tenant RAG platform.",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        "version": "1.0.0",
    },
    "variable": [
        {"key": "baseUrl", "value": "http://localhost:8000", "type": "string"},
        {"key": "apiKey", "value": "tr_dev_test_key", "type": "string"},
        {"key": "workspaceId", "value": "00000000-0000-0000-0000-000000000000", "type": "string"},
    ],
    "auth": {
        "type": "apikey",
        "apikey": [
            {"key": "key", "value": "X-API-Key", "type": "string"},
            {"key": "value", "value": "{{apiKey}}", "type": "string"},
            {"key": "in", "value": "header", "type": "string"},
        ],
    },
    "item": [
        {
            "name": "Health & Monitoring",
            "item": [
                {
                    "name": "Liveness Probe",
                    "request": {
                        "method": "GET",
                        "url": {"raw": "{{baseUrl}}/health/live", "host": ["{{baseUrl}}"], "path": ["health", "live"]},
                    },
                },
                {
                    "name": "Readiness Probe",
                    "request": {
                        "method": "GET",
                        "url": {"raw": "{{baseUrl}}/health/ready", "host": ["{{baseUrl}}"], "path": ["health", "ready"]},
                    },
                },
            ],
        },
        {
            "name": "Workspaces",
            "item": [
                {
                    "name": "List Workspaces",
                    "request": {
                        "method": "GET",
                        "url": {"raw": "{{baseUrl}}/api/v1/workspaces", "host": ["{{baseUrl}}"], "path": ["api", "v1", "workspaces"]},
                    },
                },
                {
                    "name": "Create Workspace",
                    "request": {
                        "method": "POST",
                        "url": {"raw": "{{baseUrl}}/api/v1/workspaces", "host": ["{{baseUrl}}"], "path": ["api", "v1", "workspaces"]},
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps({"name": "New Workspace", "description": "Docs and manuals"}, indent=2),
                            "options": {"raw": {"language": "json"}},
                        },
                    },
                },
            ],
        },
        {
            "name": "Chat & Retrieval",
            "item": [
                {
                    "name": "Submit Query (Blocking)",
                    "request": {
                        "method": "POST",
                        "url": {
                            "raw": "{{baseUrl}}/api/v1/workspaces/{{workspaceId}}/chat",
                            "host": ["{{baseUrl}}"],
                            "path": ["api", "v1", "workspaces", "{{workspaceId}}", "chat"],
                        },
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps({"query": "What are the contractual payment terms?", "grounding_mode": "Balanced"}, indent=2),
                            "options": {"raw": {"language": "json"}},
                        },
                    },
                },
                {
                    "name": "Chat Stream (SSE)",
                    "request": {
                        "method": "POST",
                        "url": {
                            "raw": "{{baseUrl}}/api/v1/workspaces/{{workspaceId}}/chat/stream",
                            "host": ["{{baseUrl}}"],
                            "path": ["api", "v1", "workspaces", "{{workspaceId}}", "chat", "stream"],
                        },
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps({"query": "Summarize key SLA metrics", "grounding_mode": "Strict"}, indent=2),
                            "options": {"raw": {"language": "json"}},
                        },
                    },
                },
            ],
        },
        {
            "name": "Webhook Plugins",
            "item": [
                {
                    "name": "List Plugins",
                    "request": {
                        "method": "GET",
                        "url": {
                            "raw": "{{baseUrl}}/api/v1/workspaces/{{workspaceId}}/plugins",
                            "host": ["{{baseUrl}}"],
                            "path": ["api", "v1", "workspaces", "{{workspaceId}}", "plugins"],
                        },
                    },
                },
                {
                    "name": "Register Plugin",
                    "request": {
                        "method": "POST",
                        "url": {
                            "raw": "{{baseUrl}}/api/v1/workspaces/{{workspaceId}}/plugins",
                            "host": ["{{baseUrl}}"],
                            "path": ["api", "v1", "workspaces", "{{workspaceId}}", "plugins"],
                        },
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps({
                                "name": "Custom Parser Webhook",
                                "endpoint_url": "https://service.internal/webhook",
                                "hooks": ["ON_PARSE", "ON_POST_GENERATE"],
                                "timeout_ms": 2000,
                            }, indent=2),
                            "options": {"raw": {"language": "json"}},
                        },
                    },
                },
            ],
        },
    ],
}


def main() -> None:
    out_path = Path(__file__).resolve().parent.parent / "docs" / "titanrag_postman_collection.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(POSTMAN_COLLECTION, f, indent=2)
    print(f"Generated Postman collection at {out_path}")


if __name__ == "__main__":
    main()
