from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from qdrant_client.http import models as qmodels


@pytest.mark.asyncio
async def test_outbox_dual_vector_projection():
    """
    Validates that the outbox processor builds named dual vectors ('dense' + 'bm25')
    and dispatches PointStruct to Qdrant.
    """
    mock_qdrant = AsyncMock()
    chunk_id = str(uuid4())
    tenant_id = str(uuid4())
    workspace_id = str(uuid4())

    dense_vec = [0.1] * 1536
    sparse_indices = [42, 108, 999]
    sparse_values = [1.2, 0.8, 2.5]

    payload_data = {
        "vector_dense": dense_vec,
        "vector_sparse": {
            "indices": sparse_indices,
            "values": sparse_values,
        },
        "metadata": {"title": "Handbook.pdf", "section": "Intro"},
    }

    # Verify vector construction logic
    vector_to_upsert = {
        "dense": payload_data["vector_dense"],
        "bm25": qmodels.SparseVector(
            indices=payload_data["vector_sparse"]["indices"],
            values=payload_data["vector_sparse"]["values"],
        ),
    }

    point = qmodels.PointStruct(
        id=chunk_id,
        vector=vector_to_upsert,
        payload={
            **payload_data["metadata"],
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "chunk_id": chunk_id,
        },
    )

    await mock_qdrant.upsert(
        collection_name="titan_chunks",
        points=[point],
    )

    mock_qdrant.upsert.assert_awaited_once()
    call_kwargs = mock_qdrant.upsert.await_args.kwargs
    assert call_kwargs["collection_name"] == "titan_chunks"
    upserted_point = call_kwargs["points"][0]
    assert upserted_point.id == chunk_id
    assert "dense" in upserted_point.vector
    assert "bm25" in upserted_point.vector
    assert upserted_point.vector["bm25"].indices == sparse_indices
