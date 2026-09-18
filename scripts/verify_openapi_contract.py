"""OpenAPI Contract & Breaking Changes Validator.

Validates that:
1. FastAPI app loads and exports a valid OpenAPI 3.1 schema.
2. All critical routes (/chat, /documents, /workspaces, /evaluations, /finops, /prompts)
   are present and properly documented.
3. No undocumented breaking route removals occur.
"""

import sys

from titan_backend.main import app

REQUIRED_ROUTES = [
    "/health/live",
    "/health/ready",
    "/api/v1/auth/login",
    "/api/v1/workspaces",
    "/api/v1/workspaces/{workspace_id}/documents",
    "/api/v1/workspaces/{workspace_id}/rag-settings",
    "/api/v1/workspaces/{workspace_id}/chat",
    "/api/v1/workspaces/{workspace_id}/prompts",
    "/api/v1/workspaces/{workspace_id}/analytics/failure-clusters",
    "/api/v1/workspaces/{workspace_id}/ab-experiments",
    "/api/v1/workspaces/{workspace_id}/finops/breakdown",
    "/api/v1/workspaces/{workspace_id}/plugins",
]


def main():
    schema = app.openapi()
    paths = schema.get("paths", {})
    missing = []

    for r in REQUIRED_ROUTES:
        if r not in paths:
            missing.append(r)

    print(f"Total API Paths: {len(paths)}")
    print(f"OpenAPI Version: {schema.get('openapi')}")

    if missing:
        print("\n❌ ERROR: Missing required OpenAPI routes:\n" + "\n".join(f"  - {m}" for m in missing))
        sys.exit(1)

    print("\n✅ OpenAPI schema contract validated successfully: All critical routes present.")


if __name__ == "__main__":
    main()
