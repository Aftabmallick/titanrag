import hashlib
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from titan_backend.db.models.ab_testing import ABExperiment, ABExperimentStatus

logger = structlog.get_logger(__name__)


class ABExperimentRouter:
    @staticmethod
    def get_variant_bucket(experiment_id: UUID, user_id: UUID) -> int:
        """Determines deterministically if user falls into TREATMENT or CONTROL."""
        hasher = hashlib.sha256(f"{experiment_id}:{user_id}".encode())
        hash_val = int(hasher.hexdigest(), 16) % 100
        return hash_val

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
