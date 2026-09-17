from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from titan_backend.db.models.finops import FinOpsLedger, FinOpsOperation
from titan_backend.services.finops.calculator import calculate_compute_units, calculate_dollar_cost

logger = structlog.get_logger(__name__)


class FinOpsLedgerService:
    @staticmethod
    async def record_transaction(
        session: AsyncSession,
        tenant_id: UUID,
        workspace_id: UUID,
        operation_type: FinOpsOperation,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        gpu_seconds: float = 0.0,
        ocr_pages: int = 0,
        contextual_windows: int = 0,
        colpali_pages: int = 0,
        rerank_calls: int = 0,
        user_id: UUID | None = None,
        request_id: str | None = None,
        model_name: str | None = None,
        provider: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> FinOpsLedger:
        cu = calculate_compute_units(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            ocr_pages=ocr_pages,
            contextual_windows=contextual_windows,
            colpali_pages=colpali_pages,
            rerank_calls=rerank_calls,
        )
        cost = calculate_dollar_cost(cu)

        record = FinOpsLedger(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            user_id=user_id,
            request_id=request_id,
            operation_type=operation_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            gpu_seconds=gpu_seconds,
            compute_units=cu,
            dollar_cost=cost,
            model_name=model_name,
            provider=provider,
            details=details or {},
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        return record

    @staticmethod
    async def get_workspace_breakdown(
        session: AsyncSession,
        workspace_id: UUID,
        days: int = 30,
    ) -> dict[str, Any]:
        since = datetime.now(UTC) - timedelta(days=days)

        # Aggregate total CU and cost
        totals_stmt = select(
            func.coalesce(func.sum(FinOpsLedger.compute_units), 0.0).label("total_cu"),
            func.coalesce(func.sum(FinOpsLedger.dollar_cost), 0.0).label("total_cost"),
            func.coalesce(func.sum(FinOpsLedger.prompt_tokens), 0).label("total_prompt_tokens"),
            func.coalesce(func.sum(FinOpsLedger.completion_tokens), 0).label("total_completion_tokens"),
        ).where(
            FinOpsLedger.workspace_id == workspace_id,
            FinOpsLedger.created_at >= since,
        )
        totals_res = (await session.execute(totals_stmt)).one()

        # Breakdown by operation type
        op_stmt = (
            select(
                FinOpsLedger.operation_type,
                func.coalesce(func.sum(FinOpsLedger.compute_units), 0.0).label("cu"),
                func.coalesce(func.sum(FinOpsLedger.dollar_cost), 0.0).label("cost"),
                func.count(FinOpsLedger.id).label("count"),
            )
            .where(
                FinOpsLedger.workspace_id == workspace_id,
                FinOpsLedger.created_at >= since,
            )
            .group_by(FinOpsLedger.operation_type)
        )
        op_rows = (await session.execute(op_stmt)).all()

        ingestion_ops = {
            FinOpsOperation.INGESTION_DOCLING,
            FinOpsOperation.INGESTION_EMBEDDING,
            FinOpsOperation.COLPALI_VISION,
        }
        retrieval_ops = {
            FinOpsOperation.CHAT_FAST,
            FinOpsOperation.CHAT_DEEP,
            FinOpsOperation.RERANK,
            FinOpsOperation.EVALUATION,
        }

        ingestion_cu = 0.0
        retrieval_cu = 0.0
        operations_breakdown = []

        for row in op_rows:
            op_name = row.operation_type.value if hasattr(row.operation_type, "value") else str(row.operation_type)
            operations_breakdown.append(
                {
                    "operation": op_name,
                    "compute_units": float(row.cu),
                    "cost_usd": float(row.cost),
                    "count": row.count,
                }
            )
            if row.operation_type in ingestion_ops:
                ingestion_cu += float(row.cu)
            elif row.operation_type in retrieval_ops:
                retrieval_cu += float(row.cu)

        return {
            "period_days": days,
            "total_compute_units": float(totals_res.total_cu),
            "total_dollar_cost": float(totals_res.total_cost),
            "total_prompt_tokens": totals_res.total_prompt_tokens,
            "total_completion_tokens": totals_res.total_completion_tokens,
            "ingestion_compute_units": ingestion_cu,
            "retrieval_compute_units": retrieval_cu,
            "operations": operations_breakdown,
        }
