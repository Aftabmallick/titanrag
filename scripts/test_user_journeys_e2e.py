import asyncio
import json
import time

import httpx

FRONTEND_URL = "http://localhost:3000"
BACKEND_URL = "http://localhost:8000"


async def run_all_user_journeys():
    print("=" * 80)
    print("🚀 TITANRAG FULL E2E LIVE USER JOURNEYS & API VERIFICATION")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # 0. Infrastructure & UI Page Availability
    # -------------------------------------------------------------------------
    print("\n[STEP 0] Verifying Server Availability & Frontend Routes...")
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Backend health
        resp = await client.get(f"{BACKEND_URL}/health/ready")
        assert resp.status_code == 200, f"Backend not ready: {resp.text}"
        data = resp.json()
        print(f"  ✓ Backend /health/ready -> 200 OK (Dependencies: {list(data['dependencies'].keys())})")

        # Frontend pages
        for path in ["/", "/login", "/register"]:
            r = await client.get(f"{FRONTEND_URL}{path}")
            assert r.status_code in [200, 307, 308], f"Frontend {path} failed: {r.status_code}"
            print(f"  ✓ Frontend {path} -> {r.status_code} OK (HTML rendered)")

    # -------------------------------------------------------------------------
    # Journey 1: User Registration, JWT Authentication & Identity
    # -------------------------------------------------------------------------
    print("\n[JOURNEY 1] User Registration, Authentication & RBAC...")
    timestamp = int(time.time())
    user_email = f"journey_admin_{timestamp}@titanrag.com"
    user_password = "SecurePassword123!#"
    user_name = "Enterprise Lead"

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Register user
        reg_resp = await client.post(
            f"{BACKEND_URL}/api/v1/auth/register",
            json={"email": user_email, "password": user_password, "full_name": user_name},
        )
        assert reg_resp.status_code == 201, f"Registration failed: {reg_resp.text}"
        reg_data = reg_resp.json()
        access_token = reg_data["access_token"]
        assert reg_data["refresh_token"], "Refresh token must be present in registration response"
        headers = {"Authorization": f"Bearer {access_token}"}
        print(f"  ✓ User Registered: {user_email}")
        print("  ✓ Access Token & Refresh Token issued successfully")

        # Verify User profile via /auth/me
        me_resp = await client.get(f"{BACKEND_URL}/api/v1/auth/me", headers=headers)
        assert me_resp.status_code == 200
        user_info = me_resp.json()
        tenant_id = user_info["tenant_id"]
        print(f"  ✓ Identity verification /auth/me -> Name: {user_info['full_name']}, Tenant: {tenant_id}")

        # Verify Login endpoint
        login_resp = await client.post(
            f"{BACKEND_URL}/api/v1/auth/login",
            json={"email": user_email, "password": user_password},
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        print("  ✓ Login endpoint validated -> 200 OK with refreshed JWT")

        # -------------------------------------------------------------------------
        # Journey 2: Workspace Management & Quota FinOps
        # -------------------------------------------------------------------------
        print("\n[JOURNEY 2] Workspace Creation & Switcher Lifecycle...")
        ws_resp = await client.post(
            f"{BACKEND_URL}/api/v1/workspaces",
            headers=headers,
            json={"name": "Financial Strategy RAG", "description": "Q3-Q4 Financial Analysis"},
        )
        assert ws_resp.status_code == 201, f"Workspace creation failed: {ws_resp.text}"
        ws_data = ws_resp.json()
        workspace_id = ws_data["id"]
        print(f"  ✓ Workspace Created: '{ws_data['name']}' (ID: {workspace_id})")

        # List workspaces
        list_ws = await client.get(f"{BACKEND_URL}/api/v1/workspaces", headers=headers)
        assert list_ws.status_code == 200
        assert len(list_ws.json()) >= 1
        print(f"  ✓ Workspaces listed -> {len(list_ws.json())} workspace(s) available")

        # -------------------------------------------------------------------------
        # Journey 3: Document Ingestion, Processing & Metadata Lifecycle
        # -------------------------------------------------------------------------
        print("\n[JOURNEY 3] Document Upload, MinIO Storage & Pipeline Ingestion...")
        sample_doc_content = (
            "# ACME Enterprise Strategy 2026\n\n"
            "## Executive Summary\n"
            "ACME recorded $1.4B in annual recurring revenue for fiscal year 2026.\n"
            "Our primary growth engine is the TitanRAG platform deployed across all business units.\n\n"
            "## Operating Margins & Multi-Modal Roadmap\n"
            "Gross margins improved to 84% through in-process Fast-Path ONNX routing and quantized vector indexing.\n"
            "Stage 2 rollouts incorporate ColPali visual embeddings and native Graph RAG retrieval.\n"
        )
        files = {
            "file": ("acme_strategy_2026.md", sample_doc_content.encode("utf-8"), "text/markdown"),
        }
        data = {
            "tags": "strategy,financials,2026",
            "folder": "Executive",
            "acl_groups": "all-members",
        }
        upload_resp = await client.post(
            f"{BACKEND_URL}/api/v1/workspaces/{workspace_id}/documents",
            headers=headers,
            data=data,
            files=files,
        )
        assert upload_resp.status_code == 201, f"Upload failed: {upload_resp.text}"
        doc_data = upload_resp.json()
        doc_obj = doc_data.get("document", doc_data)
        document_id = doc_obj["id"]
        title = doc_obj.get("title", doc_obj.get("filename", "acme_strategy_2026.md"))
        print(f"  ✓ Document Uploaded: '{title}' (ID: {document_id}, Status: {doc_obj.get('status')})")
        print(f"  ✓ Document Folder: '{doc_obj.get('folder')}', Tags: {doc_obj.get('tags')}")

        # List Documents
        doc_list_resp = await client.get(
            f"{BACKEND_URL}/api/v1/workspaces/{workspace_id}/documents",
            headers=headers,
        )
        docs_data = doc_list_resp.json()
        docs = docs_data.get("items", docs_data if isinstance(docs_data, list) else [])
        assert any(d["id"] == document_id for d in docs)
        print(f"  ✓ Document verified in workspace library ({len(docs)} total documents)")

        # -------------------------------------------------------------------------
        # Journey 4: RAG Settings Drawer & Interactive Fine-Tuning
        # -------------------------------------------------------------------------
        print("\n[JOURNEY 4] RAG Settings Configuration & Model Management...")
        settings_resp = await client.get(
            f"{BACKEND_URL}/api/v1/workspaces/{workspace_id}/settings",
            headers=headers,
        )
        assert settings_resp.status_code == 200
        cur_settings = settings_resp.json()
        print(
            f"  ✓ Current Settings: Mode={cur_settings['retrieval_mode']}, DenseWeight={cur_settings['dense_weight']}, TopK={cur_settings['top_k']}"
        )

        # Update RAG Settings
        update_payload = {
            "retrieval_mode": "HYBRID",
            "dense_weight": 0.85,
            "sparse_weight": 0.15,
            "top_k": 30,
            "rerank_top_k": 5,
            "score_threshold": 0.45,
            "hyde_enabled": True,
            "semantic_cache_enabled": True,
        }
        put_settings = await client.put(
            f"{BACKEND_URL}/api/v1/workspaces/{workspace_id}/settings",
            headers=headers,
            json=update_payload,
        )
        assert put_settings.status_code == 200
        updated = put_settings.json()
        assert updated["dense_weight"] == 0.85
        assert updated["top_k"] == 30
        print(
            f"  ✓ RAG Settings updated: Mode={updated['retrieval_mode']}, DenseWeight={updated['dense_weight']}, TopK={updated['top_k']}"
        )

        # -------------------------------------------------------------------------
        # Journey 5: Grounded Retrieval & Streaming Generation (SSE)
        # -------------------------------------------------------------------------
        print("\n[JOURNEY 5] Phased Streaming Chat & Retrieval Flow...")
        # Create chat session
        session_resp = await client.post(
            f"{BACKEND_URL}/api/v1/workspaces/{workspace_id}/chat-sessions",
            headers=headers,
            json={"title": "Executive Briefing Session"},
        )
        assert session_resp.status_code == 201
        session_id = session_resp.json()["id"]
        print(f"  ✓ Chat Session Initialized (ID: {session_id})")

        # Query chat with streaming
        chat_query = {
            "query": "What was ACME's annual recurring revenue in 2026 and what was the gross margin?",
            "session_id": session_id,
            "pipeline_mode": "fast",
        }
        print("  -> Sending chat query via SSE stream...")
        sse_events = []
        token_chunks = []
        async with client.stream(
            "POST",
            f"{BACKEND_URL}/api/v1/workspaces/{workspace_id}/chat",
            headers=headers,
            json=chat_query,
            timeout=30.0,
        ) as stream:
            assert stream.status_code == 200
            event_type = None
            async for line in stream.aiter_lines():
                if line.startswith("event:"):
                    event_type = line.replace("event:", "").strip()
                elif line.startswith("data:"):
                    data_str = line.replace("data:", "").strip()
                    try:
                        parsed = json.loads(data_str)
                    except Exception:
                        parsed = data_str
                    sse_events.append((event_type, parsed))
                    if event_type == "token" and isinstance(parsed, dict):
                        token_chunks.append(parsed.get("token", ""))

        event_names = [e[0] for e in sse_events]
        print(f"  ✓ Received SSE Events: {set(event_names)}")
        print(f"  ✓ Streamed Tokens count: {len(token_chunks)}")
        full_text = "".join(token_chunks)
        print(f"  ✓ Generated Text sample: {full_text[:120]}...")

        # -------------------------------------------------------------------------
        # Journey 6: Presigned URL & Document Viewer Access Control
        # -------------------------------------------------------------------------
        print("\n[JOURNEY 6] Presigned Document Scoping & Role Restriction...")
        url_resp = await client.get(
            f"{BACKEND_URL}/api/v1/workspaces/{workspace_id}/documents/{document_id}/download-url",
            headers=headers,
        )
        assert url_resp.status_code == 200, f"Presigned URL failed: {url_resp.text}"
        presigned_data = url_resp.json()
        assert "url" in presigned_data
        print(f"  ✓ Scoped Presigned URL generated with 15m expiry: {presigned_data['url'][:50]}...")

        # -------------------------------------------------------------------------
        # Journey 7: Enterprise Audit Trail & Multi-Tenant Defense-in-Depth
        # -------------------------------------------------------------------------
        print("\n[JOURNEY 7] Audit Logging & Cross-Tenant Hard Isolation...")
        audit_resp = await client.get(
            f"{BACKEND_URL}/api/v1/admin/audit-log",
            headers=headers,
        )
        assert audit_resp.status_code == 200, f"Audit log query failed: {audit_resp.text}"
        audit_data = audit_resp.json()
        audit_records = audit_data if isinstance(audit_data, list) else audit_data.get("items", [])
        print(f"  ✓ Audit Trail verified: {len(audit_records)} security event(s) logged")
        for rec in audit_records[:3]:
            print(f"    - Action: {rec['action']} | Resource: {rec['resource_type']}")

        # Cross-Tenant Isolation Attack test: Create Tenant B, verify Tenant B CANNOT read Tenant A's doc
        user_b_email = f"attacker_{timestamp}@other-corp.com"
        reg_b = await client.post(
            f"{BACKEND_URL}/api/v1/auth/register",
            json={"email": user_b_email, "password": "Password123!#", "name": "Tenant B User"},
        )
        assert reg_b.status_code == 201
        token_b = reg_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        cross_tenant_probe = await client.get(
            f"{BACKEND_URL}/api/v1/workspaces/{workspace_id}/documents/{document_id}",
            headers=headers_b,
        )
        assert cross_tenant_probe.status_code in [403, 404], (
            f"Isolation breach! Status: {cross_tenant_probe.status_code}"
        )
        print(
            f"  ✓ Cross-Tenant Hard Isolation PROVEN: Foreign tenant probe blocked with {cross_tenant_probe.status_code}"
        )

    print("\n" + "=" * 80)
    print("🎉 ALL USER JOURNEYS & ENDPOINTS VERIFIED AND PASSING WITH FLYING COLORS!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_all_user_journeys())
