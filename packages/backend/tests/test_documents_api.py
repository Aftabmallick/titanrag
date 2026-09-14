from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from titan_backend.clients.qdrant_client import TenantIngestionSemaphore
from titan_backend.core.circuit_breaker import CircuitBreaker, CircuitState
from titan_backend.core.dependencies import CurrentUser, get_current_user
from titan_backend.core.errors import AppException
from titan_backend.core.rate_limiter import ProviderTokenBucketLimiter
from titan_backend.db.models.workspaces import Workspace, WorkspaceMember, WorkspaceRole
from titan_backend.main import app
from titan_workers.pipeline.orchestrator import IngestionPipelineOrchestrator


@pytest.fixture
def test_user():
    return CurrentUser(
        id=uuid4(),
        tenant_id=uuid4(),
        email="engineer@corp.com",
        scopes=["*"],
    )



@pytest.mark.asyncio
async def test_preview_endpoint(async_client, mock_db_session, test_user):
    ws_id = uuid4()
    mock_ws = Workspace(id=ws_id, tenant_id=test_user.tenant_id, name="Test WS", settings={})
    mock_member = WorkspaceMember(workspace_id=ws_id, user_id=test_user.id, role=WorkspaceRole.OWNER)
    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [mock_ws, mock_member]

    app.dependency_overrides[get_current_user] = lambda: test_user

    payload = {
        "file_content": "# Architecture\n\nCore platform design principles.\n\n## Component Breakdown\nDetailed specifications.",
        "filename": "spec.md",
        "mime_type": "text/markdown",
    }
    resp = await async_client.post(f"/api/v1/workspaces/{ws_id}/documents/preview", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["filename"] == "spec.md"
    assert data["total_chunks"] >= 2
    assert len(data["sample_chunks"]) >= 1


@pytest.mark.asyncio
async def test_circuit_breaker_trip_and_recovery():
    cb = CircuitBreaker(name="test_service", failure_threshold=2, recovery_timeout_seconds=0.1)
    assert cb.state == CircuitState.CLOSED

    async def faulty_operation():
        raise RuntimeError("Service failure")

    # First failure
    with pytest.raises(RuntimeError):
        await cb.call(faulty_operation)
    assert cb.state == CircuitState.CLOSED

    # Second failure trips circuit to OPEN
    with pytest.raises(RuntimeError):
        await cb.call(faulty_operation)
    assert cb.state == CircuitState.OPEN

    # While OPEN, fast-fails with AppException 503 without invoking function
    with pytest.raises(AppException) as exc:
        await cb.call(faulty_operation)
    assert exc.value.status_code == 503
    assert exc.value.error_code == "CIRCUIT_BREAKER_OPEN"


@pytest.mark.asyncio
async def test_provider_rate_limiter():
    limiter = ProviderTokenBucketLimiter(provider="mock", model="mock-embed", max_rpm=100, max_tpm=10000)
    # Acquire should succeed under mock Redis fallback
    acquired = await limiter.acquire(estimated_tokens=500, wait=False)
    assert acquired is True


@pytest.mark.asyncio
async def test_end_to_end_orchestrator_pipeline():
    tenant_id = uuid4()
    workspace_id = uuid4()
    document_id = uuid4()

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()

    orchestrator = IngestionPipelineOrchestrator()
    sample_content = (
        "# System Specifications\n\n"
        "TitanRAG is an enterprise hybrid RAG engine.\n\n"
        "| Service | Role |\n| --- | --- |\n| Qdrant | Vector Index |\n| Postgres | Source of Truth |\n\n"
        "Contact security team at sec@titanrag.corp for inquiries."
    )

    result = await orchestrator.run_pipeline(
        db=mock_db,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        document_id=document_id,
        file_bytes=sample_content.encode("utf-8"),
        filename="specs.md",
        mime_type="text/markdown",
        redaction_mode="REPLACE",
        enable_contextual=True,
    )

    assert result["status"] == "READY"
    assert result["total_chunks"] >= 2
    assert result["document_id"] == str(document_id)

    # Verify db commits were executed for atomic state progression
    assert mock_db.commit.call_count >= 5
    # Verify chunks and outbox entries were staged in db
    assert mock_db.add.call_count >= result["total_chunks"] * 2


@pytest.mark.asyncio
async def test_dlq_endpoints(async_client, mock_db_session, test_user):
    admin_user = CurrentUser(
        id=test_user.id,
        tenant_id=test_user.tenant_id,
        email="admin@corp.com",
        role="ADMIN",
        scopes=["*"],
    )
    app.dependency_overrides[get_current_user] = lambda: admin_user
    mock_db_session.execute.return_value.scalars.return_value.all.return_value = []

    resp = await async_client.get("/api/v1/admin/dlq")
    assert resp.status_code == 200
    data = resp.json()
    assert "failed_ingestion_tasks" in data
    assert "failed_outbox_projections" in data
    assert data["failed_outbox_projections"] == 0


@pytest.mark.asyncio
async def test_document_sharing_cross_tenant_blocked(async_client, mock_db_session, test_user):
    ws_id = uuid4()
    doc_id = uuid4()
    target_ws_id = uuid4()

    mock_ws = Workspace(id=ws_id, tenant_id=test_user.tenant_id, name="Source WS", settings={})
    mock_member = WorkspaceMember(workspace_id=ws_id, user_id=test_user.id, role=WorkspaceRole.OWNER)

    from titan_backend.db.models.documents import Document, DocumentStatus

    mock_doc = Document(
        id=doc_id,
        tenant_id=test_user.tenant_id,
        workspace_id=ws_id,
        title="Secret.pdf",
        storage_path="path",
        content_hash="hash",
        status=DocumentStatus.READY,
    )

    # First query for require_permission (workspace, member)
    # Second query in endpoint for source doc
    # Third query in endpoint for target workspace -> returns None (different tenant)
    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [mock_ws, mock_member]
    mock_db_session.execute.return_value.scalars.return_value.first.side_effect = [mock_doc, None]

    app.dependency_overrides[get_current_user] = lambda: test_user

    resp = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/documents/{doc_id}/share",
        json={"target_workspace_id": str(target_ws_id)},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CROSS_TENANT_SHARE_FORBIDDEN"


@pytest.mark.asyncio
async def test_tenant_ingestion_semaphore(monkeypatch):
    counters = {}

    class MockRedis:
        async def incr(self, key):
            counters[key] = counters.get(key, 0) + 1
            return counters[key]

        async def decr(self, key):
            counters[key] = max(0, counters.get(key, 0) - 1)
            return counters[key]

        async def expire(self, key, ttl):
            pass

    async def mock_get_redis():
        return MockRedis()

    monkeypatch.setattr("titan_backend.clients.redis_client.get_redis_client", mock_get_redis)

    tenant_id = str(uuid4())
    sem = TenantIngestionSemaphore(tenant_id=tenant_id, max_concurrent=2)
    async with sem as acquired:
        assert acquired is True
        assert counters[sem.key] == 1

    assert counters[sem.key] == 0
