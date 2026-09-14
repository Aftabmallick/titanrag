from typing import Any

import celery
import structlog

logger = structlog.get_logger("titanrag.worker")


class TracedTask(celery.Task):
    """Base Celery task injecting structured correlation IDs and context into logging."""

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        # Extract headers or kwargs
        headers = self.request.headers or {}
        request_id = headers.get("request_id") or kwargs.get("request_id", "async-worker")
        tenant_id = headers.get("tenant_id") or kwargs.get("tenant_id", "system")
        workspace_id = headers.get("workspace_id") or kwargs.get("workspace_id", "system")

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            task_id=self.request.id,
            task_name=self.name,
            request_id=request_id,
            tenant_id=str(tenant_id),
            workspace_id=str(workspace_id),
        )

        logger.info("task_started", args_len=len(args))
        try:
            result = super().__call__(*args, **kwargs)
            logger.info("task_completed_successfully")
            return result
        except Exception as exc:
            logger.error("task_failed", error=str(exc), exc_info=True)
            raise
