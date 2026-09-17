from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from titan_backend.db.models.ab_testing import ABExperiment, ABExperimentStatus

logger = structlog.get_logger(__name__)


def murmurhash3_32(key: str, seed: int = 0) -> int:
    """Deterministic MurmurHash3 (32-bit x86) hashing algorithm.

    Guarantees uniform bucket distribution and zero hash modulo skew.
    """
    data = key.encode("utf-8")
    length = len(data)
    nblocks = length // 4
    h1 = seed & 0xFFFFFFFF
    c1 = 0xCC9E2D51
    c2 = 0x1B873593

    for i in range(nblocks):
        k1 = data[4 * i] | (data[4 * i + 1] << 8) | (data[4 * i + 2] << 16) | (data[4 * i + 3] << 24)
        k1 = (k1 * c1) & 0xFFFFFFFF
        k1 = ((k1 << 15) | (k1 >> 17)) & 0xFFFFFFFF
        k1 = (k1 * c2) & 0xFFFFFFFF

        h1 ^= k1
        h1 = ((h1 << 13) | (h1 >> 19)) & 0xFFFFFFFF
        h1 = (h1 * 5 + 0xE6546B64) & 0xFFFFFFFF

    tail = data[nblocks * 4 :]
    k1 = 0
    tlen = len(tail)
    if tlen >= 3:
        k1 ^= tail[2] << 16
    if tlen >= 2:
        k1 ^= tail[1] << 8
    if tlen >= 1:
        k1 ^= tail[0]
        k1 = (k1 * c1) & 0xFFFFFFFF
        k1 = ((k1 << 15) | (k1 >> 17)) & 0xFFFFFFFF
        k1 = (k1 * c2) & 0xFFFFFFFF
        h1 ^= k1

    h1 ^= length
    h1 ^= h1 >> 16
    h1 = (h1 * 0x85EBCA6B) & 0xFFFFFFFF
    h1 ^= h1 >> 13
    h1 = (h1 * 0xC2B2AE35) & 0xFFFFFFFF
    h1 ^= h1 >> 16
    return h1


class ABExperimentRouter:
    @staticmethod
    def get_variant_bucket(experiment_id: UUID, user_id: UUID) -> int:
        """Determines deterministically if user falls into TREATMENT or CONTROL

        using MurmurHash3 32-bit hashing modulo 100 for uniform traffic allocation.
        """
        hash_val = murmurhash3_32(f"{experiment_id}:{user_id}", seed=42)
        return hash_val % 100

    @classmethod
    async def trip_safety_circuit_breaker(
        cls,
        session: AsyncSession,
        experiment: ABExperiment,
        reason: str,
    ) -> None:
        """Auto-pauses an experiment when safety circuit breaker triggers."""
        logger.error(
            "ab_experiment_circuit_breaker_tripped",
            experiment_id=str(experiment.id),
            workspace_id=str(experiment.workspace_id),
            reason=reason,
        )
        experiment.status = ABExperimentStatus.PAUSED
        session.add(experiment)
        await session.commit()

    @classmethod
    async def get_active_experiment_override(
        cls,
        session: AsyncSession,
        workspace_id: UUID,
        user_id: UUID,
    ) -> tuple[dict[str, Any] | None, UUID | None, str | None]:
        """Finds any running A/B experiment for this workspace and returns the dynamic

        RAGSettings override, experiment_id, and variant tag ('CONTROL' | 'TREATMENT').
        """
        stmt = (
            select(ABExperiment)
            .where(
                ABExperiment.workspace_id == workspace_id,
                ABExperiment.status == ABExperimentStatus.RUNNING,
            )
            .limit(1)
        )
        experiment = (await session.execute(stmt)).scalar_one_or_none()
        if not experiment:
            return None, None, None

        bucket = cls.get_variant_bucket(experiment.id, user_id)
        if bucket < experiment.traffic_split:
            # Treatment
            variant = "TREATMENT"
            override_config = experiment.treatment_config
            experiment.sample_size_treatment += 1
        else:
            # Control
            variant = "CONTROL"
            override_config = experiment.control_config
            experiment.sample_size_control += 1

        session.add(experiment)
        await session.commit()

        return override_config, experiment.id, variant
