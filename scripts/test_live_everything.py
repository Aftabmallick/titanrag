#!/usr/bin/env python3
"""
Comprehensive Live Verification Script for TitanRAG Enterprise Monorepo.
Tests live Backend (8000), Docker Infra (PG, Redis, Qdrant, MinIO),
Reference Plugin Microservice (9099), Python SDK, MCP Server, and CLI.
"""

import asyncio
import os
import subprocess
from uuid import uuid4

import httpx

BACKEND_URL = "http://localhost:8000"
PLUGIN_URL = "http://localhost:9099"
FRONTEND_URL = "http://localhost:3000"

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"


async def run_live_tests():
    print(f"\n{INFO} Starting Full Live Verification Suite...")
    client = httpx.AsyncClient(timeout=15.0)

    # -------------------------------------------------------------------------
    # 1. Health & Dependency Checks
    # -------------------------------------------------------------------------
    print(f"\n{INFO} 1. Testing Core Health & Docker Dependencies...")
    live_resp = await client.get(f"{BACKEND_URL}/health/live")
    assert live_resp.status_code == 200, f"Live check failed: {live_resp.text}"
    assert live_resp.json() == {"status": "alive"}
    print(f"  {PASS} /health/live returned 200 alive")

    ready_resp = await client.get(f"{BACKEND_URL}/health/ready")
    assert ready_resp.status_code == 200, f"Ready check failed: {ready_resp.text}"
    ready_data = ready_resp.json()
    assert ready_data["status"] == "ready"
    for dep, info in ready_data["dependencies"].items():
        assert info["status"] == "ok", f"Dependency {dep} is not ok: {info}"
        print(f"  {PASS} Dependency [{dep}] is OK (latency: {info['latency_ms']}ms)")

    metrics_resp = await client.get(f"{BACKEND_URL}/metrics")
    assert metrics_resp.status_code == 200
    assert "http_requests_total" in metrics_resp.text or "python_info" in metrics_resp.text
    print(f"  {PASS} /metrics Prometheus endpoint responsive")

    # -------------------------------------------------------------------------
    # 2. Authentication & User Management
    # -------------------------------------------------------------------------
    print(f"\n{INFO} 2. Testing Auth Flow (Register, Login, Token)...")
    email = f"test_admin_{uuid4().hex[:8]}@titanrag.internal"
    password = "SuperSecretPassword123!"

    reg_resp = await client.post(
        f"{BACKEND_URL}/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Live Test Engineer",
            "organization_name": "TitanRAG Live QA",
        },
    )
    assert reg_resp.status_code == 201, f"Register failed: {reg_resp.text}"
    token_data = reg_resp.json()
    access_token = token_data["access_token"]
    print(f"  {PASS} Registered new user [{email}] and received JWT token")

    auth_headers = {"Authorization": f"Bearer {access_token}"}
    me_resp = await client.get(f"{BACKEND_URL}/api/v1/auth/me", headers=auth_headers)
    assert me_resp.status_code == 200
    user_info = me_resp.json()
    print(f"  {PASS} /auth/me verified identity: {user_info['email']} (name: {user_info.get('full_name')})")

    # -------------------------------------------------------------------------
    # 3. Workspaces & API Keys
    # -------------------------------------------------------------------------
    print(f"\n{INFO} 3. Testing Workspaces & API Keys...")
    ws_resp = await client.post(
        f"{BACKEND_URL}/api/v1/workspaces",
        headers=auth_headers,
        json={
            "name": "Live QA Engineering Docs",
            "description": "Workspace for automated live verification",
        },
    )
    assert ws_resp.status_code == 201, f"Workspace creation failed: {ws_resp.text}"
    ws = ws_resp.json()
    workspace_id = ws["id"]
    print(f"  {PASS} Created Workspace [{ws['name']}] (ID: {workspace_id})")

    # Generate API key
    key_resp = await client.post(
        f"{BACKEND_URL}/api/v1/api-keys",
        headers=auth_headers,
        json={"name": "live-test-key", "workspace_id": workspace_id},
    )
    assert key_resp.status_code == 201, f"API key creation failed: {key_resp.text}"
    api_key_data = key_resp.json()
    api_key = (
        api_key_data.get("raw_key")
        or api_key_data.get("key")
        or api_key_data.get("secret_key")
        or api_key_data.get("api_key")
    )
    assert api_key, f"No key returned in {api_key_data}"
    print(f"  {PASS} Generated Workspace API Key: {api_key[:12]}...")

    # -------------------------------------------------------------------------
    # 4. Settings Retrieval & Update
    # -------------------------------------------------------------------------
    print(f"\n{INFO} 4. Testing RAG Settings API...")
    settings_resp = await client.get(f"{BACKEND_URL}/api/v1/workspaces/{workspace_id}/settings", headers=auth_headers)
    assert settings_resp.status_code == 200, f"Settings fetch failed: {settings_resp.text}"
    settings = settings_resp.json()
    print(f"  {PASS} Fetched RAG Settings (dense_weight: {settings.get('dense_weight')})")

    # -------------------------------------------------------------------------
    # 5. Phase 7 Plugin Registry & Micro-Hook Ping Probe
    # -------------------------------------------------------------------------
    print(f"\n{INFO} 5. Testing Phase 7 Webhook Micro-Hook Plugin System...")
    # Reference server is running on localhost:9099
    plugin_payload = {
        "name": "Live Compliance & Legal Parser Plugin",
        "endpoint_url": f"{PLUGIN_URL}/webhook",
        "webhook_secret": "reference_test_secret_key_32_bytes_len",
        "hooks": ["ON_PARSE", "ON_CHUNK", "ON_EMBED", "ON_RERANK", "ON_POST_GENERATE"],
        "timeout_ms": 2500,
        "retry_count": 2,
        "is_active": True,
    }
    reg_plug = await client.post(
        f"{BACKEND_URL}/api/v1/workspaces/{workspace_id}/plugins",
        headers=auth_headers,
        json=plugin_payload,
    )
    assert reg_plug.status_code == 201, f"Plugin registration failed: {reg_plug.text}"
    plugin_data = reg_plug.json()
    plugin_id = plugin_data["id"]
    print(f"  {PASS} Registered external plugin: {plugin_data['name']} (ID: {plugin_id})")

    # Send Live Authenticated HMAC Ping Probe to reference plugin server
    ping_resp = await client.post(
        f"{BACKEND_URL}/api/v1/workspaces/{workspace_id}/plugins/{plugin_id}/ping",
        headers=auth_headers,
    )
    assert ping_resp.status_code == 200, f"Plugin ping probe failed: {ping_resp.text}"
    ping_data = ping_resp.json()
    assert ping_data["success"] is True, f"Ping probe reported failure: {ping_data}"
    print(f"  {PASS} HMAC Signature Ping Probe SUCCEEDED (latency: {ping_data['latency_ms']}ms)")

    # Update plugin via PATCH (testing Fix 9.1 backend support)
    patch_resp = await client.patch(
        f"{BACKEND_URL}/api/v1/workspaces/{workspace_id}/plugins/{plugin_id}",
        headers=auth_headers,
        json={"name": "Updated Live Compliance Plugin", "timeout_ms": 3000},
    )
    assert patch_resp.status_code == 200, f"Plugin patch failed: {patch_resp.text}"
    assert patch_resp.json()["name"] == "Updated Live Compliance Plugin"
    print(f"  {PASS} PATCH /plugins/{plugin_id} updated configuration successfully")

    # Verify execution log entry was saved
    logs_resp = await client.get(
        f"{BACKEND_URL}/api/v1/workspaces/{workspace_id}/plugins/{plugin_id}/logs",
        headers=auth_headers,
    )
    assert logs_resp.status_code == 200, f"Logs fetch failed: {logs_resp.text}"
    logs = logs_resp.json()
    assert len(logs) >= 1, "Expected at least 1 ping execution log"
    assert logs[0]["hook_type"] == "PING"
    assert logs[0]["status_code"] == 200
    print(f"  {PASS} Plugin execution audit log verified ({len(logs)} entries recorded)")

    # -------------------------------------------------------------------------
    # 6. Python SDK Sync & Async Clients Live
    # -------------------------------------------------------------------------
    print(f"\n{INFO} 6. Testing Official Python SDK (Sync & Async with Jitter/Retry)...")
    from titanrag import AsyncTitanClient, TitanClient

    sync_sdk = TitanClient(base_url=BACKEND_URL, api_key=api_key)
    sdk_workspaces = sync_sdk.workspaces.list()
    assert len(sdk_workspaces) >= 1
    assert any(str(w.id) == str(workspace_id) for w in sdk_workspaces)
    print(f"  {PASS} Sync TitanClient listed {len(sdk_workspaces)} workspaces via live API key")

    async_sdk = AsyncTitanClient(base_url=BACKEND_URL, api_key=api_key, max_retries=3)
    async_workspaces = await async_sdk.workspaces.list()
    assert len(async_workspaces) >= 1
    print(f"  {PASS} AsyncTitanClient listed {len(async_workspaces)} workspaces with retry logic enabled")

    # Test live chat stream query via SDK
    print(f"  {INFO} Executing live streaming chat query via SDK...")
    events = list(sync_sdk.chat_stream("What are the system capabilities?", workspace_id=workspace_id))
    assert len(events) >= 1, "Expected streaming events"
    print(f"  {PASS} SDK chat_stream received {len(events)} events from live backend")

    # -------------------------------------------------------------------------
    # 7. Model Context Protocol (MCP) Server Live
    # -------------------------------------------------------------------------
    print(f"\n{INFO} 7. Testing Model Context Protocol (MCP) Server against Live Backend...")
    from titan_mcp.server import create_mcp_server

    mcp = create_mcp_server(client=sync_sdk)
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "ask_question" in tool_names
    assert "search_documents" in tool_names
    assert "list_workspaces" in tool_names
    print(f"  {PASS} MCP Server registered {len(tools)} tools: {tool_names}")

    # Call list_workspaces tool through MCP
    mcp_ws_res = await mcp.call_tool("list_workspaces", {})
    assert "Live QA Engineering Docs" in str(mcp_ws_res)
    print(f"  {PASS} MCP tool 'list_workspaces' returned live workspace data")

    # Call search_documents tool through MCP (Fix 1.2 verification)
    mcp_search_res = await mcp.call_tool(
        "search_documents", {"query": "security policy", "workspace_id": str(workspace_id)}
    )
    assert mcp_search_res is not None
    print(f"  {PASS} MCP tool 'search_documents' executed cleanly without workaround")

    # Resource templates (Fix 1.3 verification)
    templates = await mcp.list_resource_templates()
    template_uris = [t.uri_template for t in templates]
    assert "document://{workspace_id}/{document_id}" in template_uris
    print(f"  {PASS} MCP Resource Template verified: document://{{workspace_id}}/{{document_id}}")

    # -------------------------------------------------------------------------
    # 8. CLI Live Command Invocations
    # -------------------------------------------------------------------------
    print(f"\n{INFO} 8. Testing TitanRAG CLI against Live Server...")
    # Login CLI with API key
    env = os.environ.copy()
    env["TITANRAG_API_KEY"] = api_key
    env["TITANRAG_BASE_URL"] = BACKEND_URL

    cmd_ver = subprocess.run(["uv", "run", "titan", "version"], capture_output=True, text=True, env=env)
    assert cmd_ver.returncode == 0
    assert "TitanRAG CLI" in cmd_ver.stdout
    print(f"  {PASS} CLI version: {cmd_ver.stdout.strip()}")

    # Test quiet mode query (Fix 8.1 verification)
    cmd_quiet = subprocess.run(
        ["uv", "run", "titan", "query", "Hello Titan", "--workspace-id", str(workspace_id), "--quiet"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert cmd_quiet.returncode == 0, f"Quiet query failed: {cmd_quiet.stderr}"
    print(f"  {PASS} CLI query with --quiet executed (output length: {len(cmd_quiet.stdout)} chars)")

    # Test stdin pipe query (Fix 8.2 verification)
    proc = subprocess.Popen(
        ["uv", "run", "titan", "query", "--workspace-id", str(workspace_id), "--quiet"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    stdout, stderr = proc.communicate(input="Piped question via stdin")
    assert proc.returncode == 0, f"Stdin pipe query failed: {stderr}"
    print(f"  {PASS} CLI stdin pipe (cat prompt | titan query) executed successfully")

    # -------------------------------------------------------------------------
    # 9. Frontend Service Live
    # -------------------------------------------------------------------------
    print(f"\n{INFO} 9. Testing Next.js Frontend Server on port 3000...")
    front_resp = await client.get(FRONTEND_URL)
    assert front_resp.status_code == 200
    assert "<!DOCTYPE html>" in front_resp.text or "html" in front_resp.text
    print(f"  {PASS} Frontend served HTTP 200 OK at {FRONTEND_URL}")

    await client.aclose()
    print("\n\033[92m=======================================================")
    print("ALL LIVE END-TO-END VERIFICATION CHECKS PASSED (100% OK)")
    print("=======================================================\033[0m\n")


if __name__ == "__main__":
    asyncio.run(run_live_tests())
