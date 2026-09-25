import asyncio
import os
import signal
from datetime import UTC, datetime
from typing import Any

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from titan_backend.core.config import settings

# Database connection
DATABASE_URL = settings.get_database_url()
QDRANT_URL = settings.QDRANT_URL
QDRANT_API_KEY = settings.QDRANT_API_KEY

logger = structlog.get_logger("titanrag.outbox_relay")

# Graceful termination
_running = True


def handle_stop_signal(sig: int, frame: Any) -> None:
    global _running
    logger.info("received_shutdown_signal", signal=sig)
    _running = False


signal.signal(signal.SIGINT, handle_stop_signal)
signal.signal(signal.SIGTERM, handle_stop_signal)


async def run_outbox_relay() -> None:
    logger.info("starting_outbox_relay", qdrant_url=QDRANT_URL)

    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    qdrant = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    # Import ChunkOutbox and Tenant models dynamically or load table reflection
    from sqlalchemy import MetaData
    from titan_backend.clients.qdrant_client import get_collection_for_tenant, init_qdrant_collection

    metadata = MetaData()

    async with engine.connect() as conn:
        await conn.run_sync(metadata.reflect, only=["chunk_outbox", "tenants"])
    outbox_table = metadata.tables["chunk_outbox"]
    tenants_table = metadata.tables.get("tenants")
    known_collections: set[str] = {"titan_chunks"}

    while _running:
        try:
            async with session_factory() as session:
                async with session.begin():
                    # SELECT ... FOR UPDATE SKIP LOCKED
                    stmt = (
                        select(outbox_table)
                        .where(outbox_table.c.status == "PENDING")
                        .order_by(outbox_table.c.created_at.asc())
                        .limit(50)
                        .with_for_update(skip_locked=True)
                    )
                    result = await session.execute(stmt)
                    rows = result.mappings().all()

                    if not rows:
                        await asyncio.sleep(1.0)
                        continue

                    logger.info("processing_outbox_batch", count=len(rows))

                    for row in rows:
                        outbox_id = row["id"]
                        chunk_id = str(row["chunk_id"])
                        tenant_id = str(row["tenant_id"])
                        workspace_id = str(row["workspace_id"])
                        event_type = row["event_type"]
                        payload_data = row["payload"] or {}
                        attempts = row["attempts"] + 1
                        max_attempts = row["max_attempts"]

                        try:
                            # Dynamic collection routing per tenant plan (enterprise vs shared)
                            tenant_plan = "free"
                            if tenants_table is not None:
                                try:
                                    plan_stmt = select(tenants_table.c.plan).where(
                                        tenants_table.c.id == row["tenant_id"]
                                    )
                                    plan_res = await session.execute(plan_stmt)
                                    found_plan = plan_res.scalar_one_or_none()
                                    if found_plan:
                                        tenant_plan = found_plan
                                except Exception:
                                    pass

                            target_collection = get_collection_for_tenant(tenant_plan=tenant_plan, tenant_id=tenant_id)
                            if target_collection not in known_collections:
                                await init_qdrant_collection(collection_name=target_collection)
                                known_collections.add(target_collection)

                            if event_type == "UPSERT":
                                dense_vec = payload_data.get("vector_dense")
                                sparse_data = payload_data.get("vector_sparse")
                                point_payload = payload_data.get("metadata", {})
                                point_payload["tenant_id"] = tenant_id
                                point_payload["workspace_id"] = workspace_id
                                point_payload["chunk_id"] = chunk_id

                                vector_to_upsert: Any = None
                                if dense_vec and sparse_data and sparse_data.get("indices"):
                                    vector_to_upsert = {
                                        "dense": dense_vec,
                                        "bm25": qmodels.SparseVector(
                                            indices=sparse_data["indices"],
                                            values=sparse_data["values"],
                                        ),
                                    }
                                elif dense_vec:
                                    vector_to_upsert = {"dense": dense_vec}

                                if vector_to_upsert:
                                    await qdrant.upsert(
                                        collection_name=target_collection,
                                        points=[
                                            qmodels.PointStruct(
                                                id=chunk_id,
                                                vector=vector_to_upsert,
                                                payload=point_payload,
                                            )
                                        ],
                                    )
                                else:
                                    # Metadata / ACL-only update on existing vector point
                                    await qdrant.set_payload(
                                        collection_name=target_collection,
                                        payload=point_payload,
                                        points=[chunk_id],
                                    )

                            elif event_type == "DELETE":
                                await qdrant.delete(
                                    collection_name=target_collection,
                                    points_selector=qmodels.PointIdsList(points=[chunk_id]),
                                )

                            # Mark PROCESSED
                            await session.execute(
                                update(outbox_table)
                                .where(outbox_table.c.id == outbox_id)
                                .values(
                                    status="PROCESSED",
                                    attempts=attempts,
                                    processed_at=datetime.now(UTC),
                                    last_error=None,
                                )
                            )

                        except Exception as e:
                            logger.error("outbox_projection_error", outbox_id=str(outbox_id), error=str(e))
                            new_status = "FAILED" if attempts >= max_attempts else "PENDING"
                            await session.execute(
                                update(outbox_table)
                                .where(outbox_table.c.id == outbox_id)
                                .values(
                                    status=new_status,
                                    attempts=attempts,
                                    last_error=str(e),
                                )
                            )

        except Exception as err:
            logger.error("outbox_relay_loop_error", error=str(err))
            await asyncio.sleep(2.0)

    await engine.dispose()
    logger.info("outbox_relay_shutdown_complete")


if __name__ == "__main__":
    asyncio.run(run_outbox_relay())
