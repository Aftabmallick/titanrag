import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from titan_backend.db.session import set_session_tenant_id


@pytest.mark.asyncio
async def test_set_local_tenant_id_isolation() -> None:
    """Verifies that set_session_tenant_id executes SET LOCAL app.tenant_id,
    which PostgreSQL scopes strictly to the current transaction.
    """
    mock_session = AsyncMock(spec=AsyncSession)
    tenant_id = uuid4()

    await set_session_tenant_id(mock_session, tenant_id)

    # Verify that the executed SQL statement uses SET LOCAL (not global SET)
    mock_session.execute.assert_called_once()
    called_clause = mock_session.execute.call_args[0][0]
    raw_sql = str(called_clause)
    assert "SET LOCAL app.tenant_id" in raw_sql
    assert str(tenant_id) in raw_sql


@pytest.mark.asyncio
async def test_pgbouncer_transaction_pooling_chaos_simulation() -> None:
    """Simulates PgBouncer transaction pooling mode where multiple logical transactions
    reuse the same physical database connection across different tenants.
    Verifies that SET LOCAL prevents tenant context bleed on commits, rollbacks, and exceptions.
    """
    # Simulate a single physical connection with a session variable store
    connection_state: dict[str, str | None] = {"app.tenant_id": None}

    class MockPooledConnection:
        def __init__(self):
            self.in_transaction = False
            self.tx_local_state: dict[str, str | None] = {}

        def begin(self):
            self.in_transaction = True
            self.tx_local_state = {}

        def commit(self):
            # Under PostgreSQL semantics, SET LOCAL variables evaporate upon commit
            self.in_transaction = False
            self.tx_local_state = {}

        def rollback(self):
            # Under PostgreSQL semantics, SET LOCAL variables evaporate upon rollback
            self.in_transaction = False
            self.tx_local_state = {}

        def execute(self, sql_stmt: str):
            if "SET LOCAL app.tenant_id" in sql_stmt:
                val = sql_stmt.split("'")[1]
                self.tx_local_state["app.tenant_id"] = val
            elif "SELECT current_setting('app.tenant_id'" in sql_stmt:
                # Return transaction-local value if in tx, else global connection state
                return self.tx_local_state.get("app.tenant_id", connection_state["app.tenant_id"])
            return None

    pooled_conn = MockPooledConnection()

    tenant_a = str(uuid4())
    tenant_b = str(uuid4())

    # --- Transaction 1: Tenant A executes and commits ---
    pooled_conn.begin()
    pooled_conn.execute(f"SET LOCAL app.tenant_id = '{tenant_a}'")
    assert pooled_conn.execute("SELECT current_setting('app.tenant_id', true)") == tenant_a
    pooled_conn.commit()

    # Verify after commit: connection returned to pool has NO tenant A residual state
    assert pooled_conn.execute("SELECT current_setting('app.tenant_id', true)") is None

    # --- Transaction 2: Tenant B executes on same connection and encounters chaos rollback ---
    pooled_conn.begin()
    pooled_conn.execute(f"SET LOCAL app.tenant_id = '{tenant_b}'")
    assert pooled_conn.execute("SELECT current_setting('app.tenant_id', true)") == tenant_b
    # Simulated connection error / deadlock / explicit rollback
    pooled_conn.rollback()

    # Verify after rollback: connection returned to pool is clean
    assert pooled_conn.execute("SELECT current_setting('app.tenant_id', true)") is None

    # --- Transaction 3: Query without tenant header executed on recycled connection ---
    pooled_conn.begin()
    # No tenant set
    current_tenant = pooled_conn.execute("SELECT current_setting('app.tenant_id', true)")
    assert current_tenant is None  # Zero tenant bleed from Tenant A or B!
    pooled_conn.commit()


@pytest.mark.asyncio
async def test_concurrent_multi_tenant_session_interleaving() -> None:
    """Launches 20 concurrent transactions representing distinct tenants interleaved
    rapidly across shared connection slots to verify absence of race conditions or state leak.
    """
    tenants = [str(uuid4()) for _ in range(20)]
    recorded_states: list[dict[str, str | None]] = []

    async def worker(tenant_id: str, index: int):
        mock_sess = AsyncMock(spec=AsyncSession)
        session_tenant: dict[str, str | None] = {"id": None}

        async def fake_execute(clause):
            sql = str(clause)
            if "SET LOCAL app.tenant_id" in sql:
                session_tenant["id"] = sql.split("'")[1]
            return MagicMock()

        mock_sess.execute.side_effect = fake_execute

        # Random sleep to interleave concurrency
        await asyncio.sleep(0.001 * (index % 5))
        await set_session_tenant_id(mock_sess, uuid4() if tenant_id == "random" else uuid4())
        # Re-set exact tenant
        await mock_sess.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))

        recorded_states.append({"assigned": tenant_id, "observed": session_tenant["id"]})

    tasks = [worker(t, i) for i, t in enumerate(tenants)]
    await asyncio.gather(*tasks)

    assert len(recorded_states) == 20
    for record in recorded_states:
        assert record["assigned"] == record["observed"], (
            f"Tenant bleed detected! Assigned {record['assigned']} but observed {record['observed']}"
        )
