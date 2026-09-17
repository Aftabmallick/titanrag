from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.api.v1.auth import CurrentUser, get_current_user
from titan_backend.db.models.ab_testing import ABExperiment, ABExperimentStatus
from titan_backend.db.models.settings import RAGSettings
from titan_backend.db.models.workspaces import Workspace
from titan_backend.db.session import get_db

router = APIRouter(prefix="/workspaces/{workspace_id}/ab-experiments", tags=["A/B Testing"])


class CreateExperimentRequest(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    traffic_split: int = Field(50, ge=1, le=99, description="Percentage allocated to Treatment")
    treatment_config: dict[str, Any] = Field(..., description="Override RAGSettings for Treatment")
    primary_metric: str = Field("SATISFACTION_RATE", description="Target metric for hypothesis test")


class UpdateExperimentStatusRequest(BaseModel):
    status: ABExperimentStatus


class ConcludeExperimentRequest(BaseModel):
    winning_variant: str = Field(..., description="'CONTROL', 'TREATMENT', or 'INCONCLUSIVE'")
    apply_to_workspace_settings: bool = Field(
        True, description="Whether to update active RAGSettings with winning config"
    )


@router.get("")
async def list_experiments(
    workspace_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List all A/B experiments for this workspace."""
    workspace = await session.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    stmt = (
        select(ABExperiment).where(ABExperiment.workspace_id == workspace_id).order_by(ABExperiment.created_at.desc())
    )
    experiments = (await session.execute(stmt)).scalars().all()

    return {
        "experiments": [
            {
                "id": str(e.id),
                "name": e.name,
                "description": e.description,
                "status": e.status.value,
                "traffic_split": e.traffic_split,
                "sample_size_control": e.sample_size_control,
                "sample_size_treatment": e.sample_size_treatment,
                "primary_metric": e.primary_metric,
                "p_value": e.p_value,
                "statistical_significance": e.statistical_significance,
                "winning_variant": e.winning_variant,
                "start_time": e.start_time.isoformat() if e.start_time else None,
                "end_time": e.end_time.isoformat() if e.end_time else None,
            }
            for e in experiments
        ]
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_experiment(
    workspace_id: UUID,
    req: CreateExperimentRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create and configure a new A/B experiment against current workspace settings."""
    workspace = await session.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    # Fetch current RAGSettings as control
    settings_stmt = select(RAGSettings).where(RAGSettings.workspace_id == workspace_id)
    settings = (await session.execute(settings_stmt)).scalar_one_or_none()
    control_config = {}
    if settings:
        control_config = {
            "retrieval_mode": settings.retrieval_mode,
            "dense_weight": settings.dense_weight,
            "sparse_weight": settings.sparse_weight,
            "top_k": settings.top_k,
            "rerank_top_k": settings.rerank_top_k,
            "score_threshold": settings.score_threshold,
            "context_window_strategy": settings.context_window_strategy,
            "hyde_enabled": settings.hyde_enabled,
        }

    experiment = ABExperiment(
        tenant_id=current_user.tenant_id,
        workspace_id=workspace_id,
        name=req.name,
        description=req.description,
        status=ABExperimentStatus.DRAFT,
        traffic_split=req.traffic_split,
        control_config=control_config,
        treatment_config=req.treatment_config,
        primary_metric=req.primary_metric,
    )
    session.add(experiment)
    await session.commit()
    await session.refresh(experiment)

    return {
        "id": str(experiment.id),
        "name": experiment.name,
        "status": experiment.status.value,
        "message": "Experiment created in DRAFT status",
    }


@router.patch("/{experiment_id}")
async def update_experiment_status(
    workspace_id: UUID,
    experiment_id: UUID,
    req: UpdateExperimentStatusRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update status of experiment (RUNNING, PAUSED, ROLLED_BACK)."""
    experiment = await session.get(ABExperiment, experiment_id)
    if not experiment or experiment.workspace_id != workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")

    old_status = experiment.status
    experiment.status = req.status

    if req.status == ABExperimentStatus.RUNNING and not experiment.start_time:
        experiment.start_time = datetime.now(UTC)
    elif req.status in {ABExperimentStatus.CONCLUDED, ABExperimentStatus.ROLLED_BACK} and not experiment.end_time:
        experiment.end_time = datetime.now(UTC)

    session.add(experiment)
    await session.commit()
    await session.refresh(experiment)

    return {
        "id": str(experiment.id),
        "old_status": old_status.value,
        "new_status": experiment.status.value,
        "message": f"Experiment status updated to {experiment.status.value}",
    }


@router.post("/{experiment_id}/conclude")
async def conclude_experiment(
    workspace_id: UUID,
    experiment_id: UUID,
    req: ConcludeExperimentRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Conclude experiment, record winner, and optionally promote winning configuration to default RAGSettings."""
    experiment = await session.get(ABExperiment, experiment_id)
    if not experiment or experiment.workspace_id != workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")

    experiment.status = ABExperimentStatus.CONCLUDED
    experiment.end_time = datetime.now(UTC)
    experiment.winning_variant = req.winning_variant

    if req.apply_to_workspace_settings and req.winning_variant == "TREATMENT":
        settings_stmt = select(RAGSettings).where(RAGSettings.workspace_id == workspace_id)
        current_settings = (await session.execute(settings_stmt)).scalar_one_or_none()
        if current_settings and experiment.treatment_config:
            for k, v in experiment.treatment_config.items():
                if hasattr(current_settings, k):
                    setattr(current_settings, k, v)
            session.add(current_settings)

    session.add(experiment)
    await session.commit()
    await session.refresh(experiment)

    return {
        "id": str(experiment.id),
        "status": experiment.status.value,
        "winning_variant": experiment.winning_variant,
        "settings_promoted": req.apply_to_workspace_settings and req.winning_variant == "TREATMENT",
        "message": f"Experiment concluded. Winning variant: {req.winning_variant}",
    }
