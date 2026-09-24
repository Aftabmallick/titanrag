"""Unit tests for Batch API & Async Processing — Phase 10."""

from uuid import uuid4

import pytest
from titan_backend.api.v1.batch import (
    MAX_BATCH_DELETES,
    MAX_BATCH_QUERIES,
    MAX_BATCH_UPLOADS,
    BatchQueryItem,
    BatchQueryRequest,
    BatchUploadItem,
    BatchUploadRequest,
)
from titan_backend.db.models.billing import BatchJob, BatchJobStatus, BatchJobType


def test_batch_limits_and_validation():
    """Verify max item limits and pydantic constraints."""
    assert MAX_BATCH_QUERIES == 50
    assert MAX_BATCH_UPLOADS == 100
    assert MAX_BATCH_DELETES == 500

    # Valid query request
    req = BatchQueryRequest(queries=[BatchQueryItem(query=f"Question {i}") for i in range(10)])
    assert len(req.queries) == 10

    # Valid upload request
    req_upload = BatchUploadRequest(
        documents=[BatchUploadItem(url=f"https://example.com/doc{i}.pdf") for i in range(5)]
    )
    assert len(req_upload.documents) == 5


@pytest.mark.asyncio
async def test_batch_job_model_creation():
    """Verify BatchJob DB model construction and status transitions."""
    tenant_id = uuid4()
    workspace_id = uuid4()
    job_id = uuid4()

    job = BatchJob(
        id=job_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        job_type=BatchJobType.QUERY,
        status=BatchJobStatus.PENDING,
        total_items=10,
        completed_items=0,
        failed_items=0,
        webhook_delivered=False,
        input_payload={"queries": [{"query": "What is RAG?"}]},
        webhook_url="https://client.corp/webhook",
    )

    assert job.job_type == BatchJobType.QUERY
    assert job.status == BatchJobStatus.PENDING
    assert job.total_items == 10
    assert job.completed_items == 0
    assert job.webhook_delivered is False

    # Simulate transition
    job.status = BatchJobStatus.PROCESSING
    job.completed_items = 8
    job.failed_items = 2
    assert job.status == BatchJobStatus.PROCESSING
    assert job.completed_items + job.failed_items == job.total_items
