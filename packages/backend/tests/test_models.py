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


def test_feedback_and_connector_model_instantiation():
    from titan_backend.db.models.connectors import Connector, ConnectorStatus
    from titan_backend.db.models.feedback import Feedback

    t_id = uuid4()
    w_id = uuid4()
    s_id = uuid4()
    m_id = uuid4()

    fb = Feedback(
        tenant_id=t_id,
        workspace_id=w_id,
        session_id=s_id,
        message_id=m_id,
        rating=1,
        comment="Great answer!",
    )
    assert fb.rating == 1
    assert fb.comment == "Great answer!"

    conn = Connector(
        tenant_id=t_id,
        workspace_id=w_id,
        name="Google Drive Prod",
        connector_type="gdrive",
        status=ConnectorStatus.ACTIVE,
    )
    assert conn.name == "Google Drive Prod"
    assert conn.connector_type == "gdrive"
    assert conn.status == ConnectorStatus.ACTIVE
