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

# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres_dev_password@localhost:5432/titanrag",
)
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

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

    # Import ChunkOutbox model dynamically or load table reflection
    from sqlalchemy import MetaData

    metadata = MetaData()

    async with engine.connect() as conn:
        await conn.run_sync(metadata.reflect, only=["chunk_outbox"])
    outbox_table = metadata.tables["chunk_outbox"]

    collection_name = "titan_chunks"

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
                            if event_type == "UPSERT":
                                dense_vec = payload_data.get("vector_dense")
                                point_payload = payload_data.get("metadata", {})
                                point_payload["tenant_id"] = tenant_id
                                point_payload["workspace_id"] = workspace_id
                                point_payload["chunk_id"] = chunk_id

                                if dense_vec:
                                    await qdrant.upsert(
                                        collection_name=collection_name,
                                        points=[
                                            qmodels.PointStruct(
                                                id=chunk_id,
                                                vector=dense_vec,
                                                payload=point_payload,
                                            )
                                        ],
                                    )

                            elif event_type == "DELETE":
                                await qdrant.delete(
                                    collection_name=collection_name,
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
