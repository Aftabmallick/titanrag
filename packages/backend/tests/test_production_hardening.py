from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from titan_backend.core.config import settings
from titan_backend.core.dependencies import CurrentUser, get_current_user
from titan_backend.core.file_validator import scan_file_safety, scan_with_clamav
from titan_backend.db.models.workspaces import Workspace, WorkspaceMember, WorkspaceRole
from titan_backend.main import app
from titan_workers.outbox.reconciler import reconcile_vector_storage
from titan_workers.pipeline.embedding.dense_embedder import DenseEmbedder, EmbeddingServiceError


@pytest.fixture
def hardening_test_user() -> CurrentUser:
    return CurrentUser(
        id=uuid4(),
        tenant_id=uuid4(),
        email="compliance_admin@corp.com",
        scopes=["*"],
    )


@pytest.mark.asyncio
async def test_strict_embedding_failure_in_production() -> None:
    """Verifies that in production/strict mode, DenseEmbedder raises EmbeddingServiceError
    instead of silently falling back to deterministic SHA-512 embeddings when LiteLLM is unreachable.
    """
    embedder = DenseEmbedder(dimension=1536, strict_mode=True)

    with patch("httpx.AsyncClient.post", side_effect=Exception("LiteLLM connection refused")):
        with pytest.raises(EmbeddingServiceError) as exc_info:
            await embedder.embed_batch(["Hello world enterprise query"])

        assert "Failed to generate dense embeddings" in str(exc_info.value)
        assert "upstream unavailable" in str(exc_info.value) or "connection refused" in str(exc_info.value)


@pytest.mark.asyncio
async def test_embedding_dimension_validation() -> None:
    """Verifies that an invalid dimension or NaN returned by upstream triggers an immediate exception."""
    embedder = DenseEmbedder(dimension=1536, strict_mode=True)

    # Mock response returning wrong dimension (e.g. 512 instead of 1536)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": [{"embedding": [0.1] * 512}]}

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        with pytest.raises(EmbeddingServiceError) as exc_info:
            await embedder.embed_batch(["Test passage"])
        assert "Invalid embedding dimension" in str(exc_info.value)

    # Mock response returning NaN
    mock_resp_nan = MagicMock()
    mock_resp_nan.status_code = 200
    mock_resp_nan.json.return_value = {"data": [{"embedding": [float("nan")] * 1536}]}

    with patch("httpx.AsyncClient.post", return_value=mock_resp_nan):
        with pytest.raises(EmbeddingServiceError) as exc_info:
            await embedder.embed_batch(["Test passage"])
        assert "NaN detected" in str(exc_info.value)


@pytest.mark.asyncio
async def test_upload_document_storage_failure_in_production(
    async_client: AsyncClient, mock_db_session: MagicMock, hardening_test_user: CurrentUser
) -> None:
    """Verifies that MinIO failure during document upload in production mode raises 502 STORAGE_UNAVAILABLE."""
    ws_id = uuid4()
    mock_ws = Workspace(id=ws_id, tenant_id=hardening_test_user.tenant_id, name="Test WS", settings={})
    mock_member = WorkspaceMember(workspace_id=ws_id, user_id=hardening_test_user.id, role=WorkspaceRole.ADMIN)

    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [mock_ws, mock_member, 0]
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = None
    app.dependency_overrides[get_current_user] = lambda: hardening_test_user

    pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"

    with patch.object(settings, "FAIL_ON_STORAGE_ERROR", True):
        with patch("titan_backend.api.v1.documents.get_minio_client") as mock_get_minio:
            mock_minio = MagicMock()
            mock_minio.put_object.side_effect = Exception("S3 bucket unavailable or disk full")
            mock_get_minio.return_value = mock_minio

            resp = await async_client.post(
                f"/api/v1/workspaces/{ws_id}/documents",
                files={"file": ("contract.pdf", pdf_content, "application/pdf")},
            )
            assert resp.status_code == 502
            data = resp.json()
            assert data["error"]["code"] == "STORAGE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_upload_document_celery_dispatch_failure_in_production(
    async_client: AsyncClient, mock_db_session: MagicMock, hardening_test_user: CurrentUser
) -> None:
    """Verifies that Celery dispatch failure during document upload in production mode marks document FAILED and returns 503."""
    ws_id = uuid4()
    mock_ws = Workspace(id=ws_id, tenant_id=hardening_test_user.tenant_id, name="Test WS", settings={})
    mock_member = WorkspaceMember(workspace_id=ws_id, user_id=hardening_test_user.id, role=WorkspaceRole.ADMIN)

    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [mock_ws, mock_member, 0]
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = None
    app.dependency_overrides[get_current_user] = lambda: hardening_test_user

    pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"

    with patch.object(settings, "FAIL_ON_STORAGE_ERROR", True):
        with patch("titan_backend.api.v1.documents.get_minio_client") as mock_get_minio:
            mock_minio = MagicMock()
            mock_minio.put_object.return_value = None
            mock_get_minio.return_value = mock_minio

            with patch(
                "titan_workers.tasks.ingestion.process_document_pipeline.delay",
                side_effect=Exception("Broker connection error"),
            ):
                resp = await async_client.post(
                    f"/api/v1/workspaces/{ws_id}/documents",
                    files={"file": ("report.pdf", pdf_content, "application/pdf")},
                )
                assert resp.status_code == 503
                data = resp.json()
                assert data["error"]["code"] == "PIPELINE_UNAVAILABLE"


def test_reconciler_scroll_pagination() -> None:
    """Verifies that reconcile_vector_storage iterates across multiple Qdrant scroll pages."""
    mock_qclient = MagicMock()

    # Simulate 2 collections: titan_chunks
    mock_collections = MagicMock()
    mock_coll_item = MagicMock()
    mock_coll_item.name = "titan_chunks"
    mock_collections.collections = [mock_coll_item]
    mock_qclient.get_collections.return_value = mock_collections

    # Page 1: 2 points, next_offset = 'page2_offset'
    p1 = MagicMock(id=str(uuid4()))
    p2 = MagicMock(id=str(uuid4()))
    page1 = ([p1, p2], "page2_offset")

    # Page 2: 1 point, next_offset = None
    p3 = MagicMock(id=str(uuid4()))
    page2 = ([p3], None)

    mock_qclient.scroll.side_effect = [page1, page2]

    with patch("titan_workers.outbox.reconciler.create_engine") as mock_create_engine:
        mock_conn = MagicMock()
        mock_create_engine.return_value.connect.return_value.__enter__.return_value = mock_conn
        # Postgres has p1, but p2 and p3 are missing (orphans)
        mock_conn.execute.return_value.fetchall.return_value = [(str(p1.id),)]

        with patch("titan_workers.outbox.reconciler.QdrantClient", return_value=mock_qclient):
            result = reconcile_vector_storage()

            assert result["status"] == "success"
            # Total points scrolled: 2 on page1 + 1 on page2 = 3
            assert result["qdrant_points_count"] == 3
            # Orphans detected: p2 and p3 = 2
            assert result["orphans_detected"] == 2
            assert mock_qclient.scroll.call_count == 2


def test_clamav_daemon_stream_scan() -> None:
    """Verifies that scan_with_clamav correctly communicates with the daemon and detects threats."""
    # 1. Threat found
    mock_sock = MagicMock()
    mock_sock.__enter__.return_value = mock_sock
    mock_sock.recv.side_effect = [b"stream: Win.Test.EICAR_HDB-1 FOUND\n", b""]

    with patch("socket.create_connection", return_value=mock_sock):
        is_clean, threat_name = scan_with_clamav(b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR", host="localhost")
        assert not is_clean
        assert threat_name == "Win.Test.EICAR_HDB-1"

    # 2. Clean stream
    mock_sock_clean = MagicMock()
    mock_sock_clean.__enter__.return_value = mock_sock_clean
    mock_sock_clean.recv.side_effect = [b"stream: OK\n", b""]

    with patch("socket.create_connection", return_value=mock_sock_clean):
        is_clean_ok, threat_name_ok = scan_with_clamav(b"Safe business document", host="localhost")
        assert is_clean_ok
        assert threat_name_ok is None

    # 3. Integrated file safety scan with ClamAV enabled
    with patch.object(settings, "CLAMAV_HOST", "clamav.internal"):
        with patch("titan_backend.core.file_validator.scan_with_clamav", return_value=(False, "Trojan.Downloader")):
            is_safe, threats = scan_file_safety(b"malicious bytes", "invoice.pdf")
            assert not is_safe
            assert any("CLAMAV_DETECTED_Trojan.Downloader" in t for t in threats)
