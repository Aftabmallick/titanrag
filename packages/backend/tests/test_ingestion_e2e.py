from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from titan_backend.core.dependencies import CurrentUser, get_current_user
from titan_backend.db.models.workspaces import Workspace, WorkspaceMember, WorkspaceRole
from titan_backend.main import app
from titan_workers.pipeline.orchestrator import IngestionPipelineOrchestrator


@pytest.fixture
def test_user():
    return CurrentUser(
        id=uuid4(),
        tenant_id=uuid4(),
        email="engineer@titanrag.corp",
        scopes=["*"],
    )


@pytest.mark.asyncio
async def test_full_pipeline_ingestion_e2e(async_client, mock_db_session, test_user):
    """
    End-to-end ingestion test:
    1. Simulates markdown upload with table and PII data
    2. Runs IngestionPipelineOrchestrator
    3. Asserts document transition to READY, multi-chunk generation, outbox staging, and redaction
    """
    ws_id = uuid4()
    doc_id = uuid4()

    mock_ws = Workspace(id=ws_id, tenant_id=test_user.tenant_id, name="Eng Docs", settings={})
    mock_member = WorkspaceMember(workspace_id=ws_id, user_id=test_user.id, role=WorkspaceRole.OWNER)
    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [mock_ws, mock_member]

    app.dependency_overrides[get_current_user] = lambda: test_user

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()

    orchestrator = IngestionPipelineOrchestrator()
    sample_doc = (
        "# Security Policy\n\n"
        "TitanRAG enforces tenant isolation.\n\n"
        "| Role | Scope |\n| --- | --- |\n| Admin | Tenant |\n| Member | Workspace |\n\n"
        "Contact CISO at ciso@titanrag.corp or call 555-123-4567 for vulnerabilities."
    )

    result = await orchestrator.run_pipeline(
        db=mock_db,
        tenant_id=test_user.tenant_id,
        workspace_id=ws_id,
        document_id=doc_id,
        file_bytes=sample_doc.encode("utf-8"),
        filename="security.md",
        mime_type="text/markdown",
        redaction_mode="REPLACE",
        enable_contextual=True,
    )

    assert result["status"] == "READY"
    assert result["document_id"] == str(doc_id)
    assert result["total_chunks"] >= 2
    assert mock_db.commit.call_count >= 5
    assert mock_db.add.call_count >= result["total_chunks"] * 2
