from uuid import uuid4

from titan_backend.db.models.outbox import ChunkOutbox, OutboxStatus


def test_chunk_outbox_model_instantiation():
    t_id = uuid4()
    w_id = uuid4()
    c_id = uuid4()

    outbox = ChunkOutbox(
        tenant_id=t_id,
        workspace_id=w_id,
        chunk_id=c_id,
        event_type="UPSERT",
        payload={
            "vector_dense": [0.1] * 1536,
            "metadata": {"title": "Test Document"},
        },
        status=OutboxStatus.PENDING,
    )

    assert outbox.tenant_id == t_id
    assert outbox.workspace_id == w_id
    assert outbox.chunk_id == c_id
    assert outbox.event_type == "UPSERT"
    assert outbox.status == OutboxStatus.PENDING
    assert len(outbox.payload["vector_dense"]) == 1536
