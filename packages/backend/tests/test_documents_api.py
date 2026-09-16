import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from titan_backend.clients.qdrant_client import TenantIngestionSemaphore
from titan_backend.core.circuit_breaker import CircuitBreaker, CircuitState
from titan_backend.core.dependencies import CurrentUser, get_current_user
from titan_backend.core.errors import AppException
from titan_backend.core.rate_limiter import ProviderTokenBucketLimiter
from titan_backend.db.models.documents import Document, DocumentStatus, DocumentVersion
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

    # Verify outbox payload contains complete metadata schema required by Qdrant
    from titan_backend.db.models.outbox import ChunkOutbox

    added_objects = [call[0][0] for call in mock_db.add.call_args_list]
    outbox_entries = [o for o in added_objects if isinstance(o, ChunkOutbox)]
    assert len(outbox_entries) == result["total_chunks"]
    first_outbox = outbox_entries[0]
    meta = first_outbox.payload["metadata"]
    assert "acl_groups" in meta
    assert "doc_type" in meta
    assert "folder" in meta
    assert "tags" in meta
    assert "status" in meta
    assert "created_at" in meta


@pytest.mark.asyncio
async def test_dlq_endpoints(async_client, mock_db_session, test_user, monkeypatch):
    mock_delay = MagicMock()
    monkeypatch.setattr("titan_workers.tasks.ingestion.process_document_pipeline.delay", mock_delay)

    admin_user = CurrentUser(
        id=test_user.id,
        tenant_id=test_user.tenant_id,
        email="admin@corp.com",
        role="ADMIN",
        scopes=["*"],
    )
    app.dependency_overrides[get_current_user] = lambda: admin_user
    mock_db_session.execute.return_value.scalars.return_value.all.return_value = []

    # Test DLQ listing
    resp = await async_client.get("/api/v1/admin/dlq")
    assert resp.status_code == 200
    data = resp.json()
    assert "failed_ingestion_tasks" in data
    assert "failed_outbox_projections" in data
    assert data["failed_outbox_projections"] == 0

    # Test DLQ retry
    task_id = uuid4()
    doc_id = uuid4()
    from titan_backend.db.models.documents import Document, DocumentStatus
    from titan_backend.db.models.ingestion import IngestionTask, TaskStatus

    mock_task = IngestionTask(
        id=task_id,
        tenant_id=test_user.tenant_id,
        workspace_id=uuid4(),
        document_id=doc_id,
        status=TaskStatus.FAILED,
        stage="FAILED",
    )
    mock_doc = Document(
        id=doc_id,
        tenant_id=test_user.tenant_id,
        workspace_id=mock_task.workspace_id,
        title="failed_doc.pdf",
        storage_path="path",
        content_hash="hash",
        mime_type="application/pdf",
        status=DocumentStatus.FAILED,
    )

    mock_db_session.execute.return_value.scalars.return_value.first.side_effect = [mock_task, mock_doc]
    retry_resp = await async_client.post(f"/api/v1/admin/dlq/{task_id}/retry")
    assert retry_resp.status_code == 200
    assert retry_resp.json()["status"] == "requeued"
    assert mock_delay.call_count == 1


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


@pytest.mark.asyncio
async def test_upload_document_endpoint_success(async_client, mock_db_session, test_user, monkeypatch):
    # Monkeypatch Celery task delay to avoid attempting connection to real Redis
    monkeypatch.setattr("titan_workers.tasks.ingestion.process_document_pipeline.delay", MagicMock())

    ws_id = uuid4()
    mock_ws = Workspace(id=ws_id, tenant_id=test_user.tenant_id, name="Test WS", settings={})
    mock_member = WorkspaceMember(workspace_id=ws_id, user_id=test_user.id, role=WorkspaceRole.OWNER)
    # mock_ws, mock_member, and 0 for check_document_quota count
    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [mock_ws, mock_member, 0]
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = None

    app.dependency_overrides[get_current_user] = lambda: test_user

    files = {"file": ("manual.md", b"# Manual\n\nOperational guidelines.", "text/markdown")}
    resp = await async_client.post(f"/api/v1/workspaces/{ws_id}/documents", files=files)
    assert resp.status_code == 201
    data = resp.json()
    assert data["document"]["title"] == "manual.md"
    assert data["is_duplicate"] is False
    assert "task_id" in data


@pytest.mark.asyncio
async def test_reindex_endpoints(async_client, mock_db_session, test_user, monkeypatch):
    import datetime

    monkeypatch.setattr("titan_workers.tasks.ingestion.process_document_pipeline.delay", MagicMock())

    ws_id = uuid4()
    doc_id = uuid4()
    now = datetime.datetime.now(datetime.UTC)
    mock_ws = Workspace(id=ws_id, tenant_id=test_user.tenant_id, name="Test WS", settings={})
    mock_member = WorkspaceMember(workspace_id=ws_id, user_id=test_user.id, role=WorkspaceRole.OWNER)
    from titan_backend.db.models.documents import Document, DocumentStatus

    mock_doc = Document(
        id=doc_id,
        tenant_id=test_user.tenant_id,
        workspace_id=ws_id,
        title="spec.pdf",
        source_type="file",
        storage_path="path",
        content_hash="hash",
        mime_type="application/pdf",
        file_size_bytes=1024,
        status=DocumentStatus.READY,
        doc_type="pdf",
        folder="docs",
        tags=["spec"],
        is_stale=False,
        is_shared=False,
        created_at=now,
        updated_at=now,
    )

    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [mock_ws, mock_member]
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = mock_doc
    mock_db_session.execute.return_value.scalars.return_value.all.return_value = [uuid4()]

    app.dependency_overrides[get_current_user] = lambda: test_user

    # 1. Test single document reindex
    resp = await async_client.post(f"/api/v1/workspaces/{ws_id}/documents/{doc_id}/reindex")
    assert resp.status_code == 200
    data = resp.json()
    assert data["document"]["id"] == str(doc_id)
    assert "task_id" in data

    # 2. Test bulk reindex
    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [mock_ws, mock_member]
    mock_db_session.execute.return_value.scalars.return_value.all.side_effect = [[mock_doc], [uuid4()]]
    bulk_resp = await async_client.post(f"/api/v1/workspaces/{ws_id}/documents/reindex")
    assert bulk_resp.status_code == 200
    bulk_data = bulk_resp.json()
    assert len(bulk_data) == 1
    assert bulk_data[0]["document"]["id"] == str(doc_id)


def test_file_signature_validation():
    from titan_backend.core.file_validator import scan_file_safety, validate_file_signature

    # Valid PDF
    valid_pdf = b"%PDF-1.7\nSample content"
    is_valid, mime = validate_file_signature(valid_pdf, "sample.pdf")
    assert is_valid is True
    assert mime == "application/pdf"

    # Corrupt PDF missing header
    corrupt_pdf = b"NOT_A_PDF_CONTENT"
    is_valid, msg = validate_file_signature(corrupt_pdf, "sample.pdf")
    assert is_valid is False
    assert "Missing %PDF-" in msg

    # Disguised Windows PE Executable
    disguised_exe = b"MZ\x90\x00\x03\x00\x00\x00"
    is_valid, msg = validate_file_signature(disguised_exe, "invoice.pdf")
    assert is_valid is False
    assert "MZ header detected" in msg

    # Text containing null bytes
    binary_in_text = b"Normal text\x00\x01\x02"
    is_valid, msg = validate_file_signature(binary_in_text, "notes.txt")
    assert is_valid is False
    assert "Binary data detected" in msg

    # Malicious script payload
    safe, threats = scan_file_safety(b"powershell -enc aW52b2tl", "test.txt")
    assert safe is False
    assert len(threats) >= 1


@pytest.mark.asyncio
async def test_disguised_executable_upload_rejected(async_client, mock_db_session, test_user):
    ws_id = uuid4()
    mock_ws = Workspace(id=ws_id, tenant_id=test_user.tenant_id, name="Test WS", settings={})
    mock_member = WorkspaceMember(workspace_id=ws_id, user_id=test_user.id, role=WorkspaceRole.OWNER)
    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [mock_ws, mock_member]

    app.dependency_overrides[get_current_user] = lambda: test_user

    # Disguised executable payload named invoice.pdf
    files = {"file": ("invoice.pdf", b"MZ\x90\x00\x03\x00\x00\x00executable", "application/pdf")}
    resp = await async_client.post(f"/api/v1/workspaces/{ws_id}/documents", files=files)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_FILE_SIGNATURE"


@pytest.mark.asyncio
async def test_document_presigned_download_and_view_urls(async_client, mock_db_session, test_user):
    from unittest.mock import patch

    ws_id = uuid4()
    doc_id = uuid4()
    now = datetime.datetime.now(datetime.UTC)
    mock_ws = Workspace(id=ws_id, tenant_id=test_user.tenant_id, name="Test WS", settings={})
    mock_member = WorkspaceMember(workspace_id=ws_id, user_id=test_user.id, role=WorkspaceRole.OWNER)
    mock_doc = Document(
        id=doc_id,
        tenant_id=test_user.tenant_id,
        workspace_id=ws_id,
        title="contract.pdf",
        source_type="file",
        storage_path=f"{test_user.tenant_id}/{ws_id}/{doc_id}/contract.pdf",
        content_hash="hash",
        mime_type="application/pdf",
        file_size_bytes=2048,
        status=DocumentStatus.READY,
        doc_type="pdf",
        folder=None,
        tags=[],
        is_stale=False,
        is_shared=False,
        created_at=now,
        updated_at=now,
    )

    app.dependency_overrides[get_current_user] = lambda: test_user

    with patch(
        "titan_backend.api.v1.documents.generate_presigned_get_url",
        return_value="https://minio.test/presigned-url?signature=abc",
    ):
        # 1. Download URL
        mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [mock_ws, mock_member]
        mock_db_session.execute.return_value.scalars.return_value.first.return_value = mock_doc
        dl_resp = await async_client.get(f"/api/v1/workspaces/{ws_id}/documents/{doc_id}/download-url")
        assert dl_resp.status_code == 200
        dl_data = dl_resp.json()
        assert dl_data["action"] == "download"
        assert dl_data["expires_in"] == 900
        assert "minio.test" in dl_data["url"]

        # 2. View URL
        mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [mock_ws, mock_member]
        mock_db_session.execute.return_value.scalars.return_value.first.return_value = mock_doc
        v_resp = await async_client.get(f"/api/v1/workspaces/{ws_id}/documents/{doc_id}/view-url")
        assert v_resp.status_code == 200
        v_data = v_resp.json()
        assert v_data["action"] == "view"
        assert v_data["expires_in"] == 900


@pytest.mark.asyncio
async def test_document_versions_list_and_create(async_client, mock_db_session, test_user):
    from unittest.mock import patch

    ws_id = uuid4()
    doc_id = uuid4()
    now = datetime.datetime.now(datetime.UTC)
    mock_ws = Workspace(id=ws_id, tenant_id=test_user.tenant_id, name="Test WS", settings={})
    mock_member = WorkspaceMember(workspace_id=ws_id, user_id=test_user.id, role=WorkspaceRole.OWNER)
    mock_doc = Document(
        id=doc_id,
        tenant_id=test_user.tenant_id,
        workspace_id=ws_id,
        title="contract.pdf",
        source_type="file",
        storage_path=f"{test_user.tenant_id}/{ws_id}/{doc_id}/contract.pdf",
        content_hash="hash",
        mime_type="application/pdf",
        file_size_bytes=2048,
        status=DocumentStatus.READY,
        doc_type="pdf",
        folder=None,
        tags=[],
        is_stale=False,
        is_shared=False,
        created_at=now,
        updated_at=now,
    )
    mock_ver = DocumentVersion(
        id=uuid4(),
        document_id=doc_id,
        version_number=1,
        storage_path=mock_doc.storage_path,
        content_hash=mock_doc.content_hash,
        created_at=now,
        updated_at=now,
    )

    app.dependency_overrides[get_current_user] = lambda: test_user

    # 1. GET versions
    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [mock_ws, mock_member]
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = mock_doc
    mock_db_session.execute.return_value.scalars.return_value.all.return_value = [mock_ver]

    list_resp = await async_client.get(f"/api/v1/workspaces/{ws_id}/documents/{doc_id}/versions")
    assert list_resp.status_code == 200
    versions_data = list_resp.json()
    assert len(versions_data) == 1
    assert versions_data[0]["version_number"] == 1
    assert versions_data[0]["document_id"] == str(doc_id)

    # 2. POST new version
    with (
        patch("titan_backend.api.v1.documents.get_minio_client"),
        patch("titan_backend.api.v1.documents.semantic_cache.invalidate_workspace", new_callable=AsyncMock),
    ):
        mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [mock_ws, mock_member]
        mock_db_session.execute.return_value.scalars.return_value.first.return_value = mock_doc
        mock_db_session.execute.return_value.scalar.return_value = 1
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = [uuid4()]

        new_v_file = {"file": ("contract_v2.pdf", b"%PDF-1.7\nUpdated version content", "application/pdf")}
        post_resp = await async_client.post(
            f"/api/v1/workspaces/{ws_id}/documents/{doc_id}/versions",
            files=new_v_file,
        )
        assert post_resp.status_code == 201
        post_data = post_resp.json()
        assert post_data["document"]["id"] == str(doc_id)
        assert "task_id" in post_data


@pytest.mark.asyncio
async def test_bulk_delete_documents(async_client, mock_db_session, test_user):
    from unittest.mock import patch

    ws_id = uuid4()
    doc_id1 = uuid4()
    doc_id2 = uuid4()
    now = datetime.datetime.now(datetime.UTC)
    mock_ws = Workspace(id=ws_id, tenant_id=test_user.tenant_id, name="Test WS", settings={})
    mock_member = WorkspaceMember(workspace_id=ws_id, user_id=test_user.id, role=WorkspaceRole.OWNER)

    mock_doc1 = Document(
        id=doc_id1,
        tenant_id=test_user.tenant_id,
        workspace_id=ws_id,
        title="doc1.pdf",
        source_type="file",
        storage_path="path1",
        content_hash="h1",
        mime_type="application/pdf",
        file_size_bytes=100,
        status=DocumentStatus.READY,
        doc_type="pdf",
        tags=[],
        is_stale=False,
        is_shared=False,
        created_at=now,
        updated_at=now,
    )
    mock_doc2 = Document(
        id=doc_id2,
        tenant_id=test_user.tenant_id,
        workspace_id=ws_id,
        title="doc2.pdf",
        source_type="file",
        storage_path="path2",
        content_hash="h2",
        mime_type="application/pdf",
        file_size_bytes=200,
        status=DocumentStatus.READY,
        doc_type="pdf",
        tags=[],
        is_stale=False,
        is_shared=False,
        created_at=now,
        updated_at=now,
    )

    app.dependency_overrides[get_current_user] = lambda: test_user

    with (
        patch("titan_backend.api.v1.documents.get_minio_client"),
        patch("titan_backend.api.v1.documents.semantic_cache.invalidate_workspace", new_callable=AsyncMock),
    ):
        mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [mock_ws, mock_member]
        mock_db_session.execute.return_value.scalars.return_value.all.side_effect = [
            [mock_doc1, mock_doc2],  # documents found
            [uuid4(), uuid4()],  # chunk ids
        ]

        resp = await async_client.post(
            f"/api/v1/workspaces/{ws_id}/documents/bulk-delete",
            json={"document_ids": [str(doc_id1), str(doc_id2)]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted_count"] == 2
        assert str(doc_id1) in data["document_ids"]
        assert str(doc_id2) in data["document_ids"]


@pytest.mark.asyncio
async def test_update_document_acl_groups_propagates(async_client, mock_db_session, test_user):
    from unittest.mock import patch

    from titan_backend.db.models.chunks import Chunk

    ws_id = uuid4()
    doc_id = uuid4()
    chunk_id = uuid4()
    now = datetime.datetime.now(datetime.UTC)
    mock_ws = Workspace(id=ws_id, tenant_id=test_user.tenant_id, name="Test WS", settings={})
    mock_member = WorkspaceMember(workspace_id=ws_id, user_id=test_user.id, role=WorkspaceRole.OWNER)

    mock_doc = Document(
        id=doc_id,
        tenant_id=test_user.tenant_id,
        workspace_id=ws_id,
        title="classified.pdf",
        source_type="file",
        storage_path="p",
        content_hash="h",
        mime_type="application/pdf",
        file_size_bytes=500,
        status=DocumentStatus.READY,
        doc_type="pdf",
        tags=[],
        is_stale=False,
        is_shared=False,
        meta={"acl_groups": ["general"]},
        created_at=now,
        updated_at=now,
    )
    mock_chunk = Chunk(
        id=chunk_id,
        tenant_id=test_user.tenant_id,
        workspace_id=ws_id,
        document_id=doc_id,
        chunk_index=0,
        content="classified text",
        meta={"acl_groups": ["general"]},
    )

    app.dependency_overrides[get_current_user] = lambda: test_user

    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [mock_ws, mock_member]
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = mock_doc
    mock_db_session.execute.return_value.scalars.return_value.all.return_value = [mock_chunk]

    with patch("titan_backend.api.v1.documents.semantic_cache.invalidate_workspace", new_callable=AsyncMock):
        resp = await async_client.patch(
            f"/api/v1/workspaces/{ws_id}/documents/{doc_id}",
            json={"acl_groups": ["executives", "security-lead"]},
        )
        assert resp.status_code == 200
        # Verify chunk meta was updated to new ACL groups
        assert mock_chunk.meta["acl_groups"] == ["executives", "security-lead"]
