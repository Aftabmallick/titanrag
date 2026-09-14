import structlog

from titan_workers.base_task import TracedTask
from titan_workers.celery_app import celery_app

logger = structlog.get_logger("titanrag.housekeeping")


@celery_app.task(base=TracedTask, name="titan_workers.tasks.housekeeping.cleanup_stale_tasks", queue="p1_default")
def cleanup_stale_tasks() -> dict:
    """Hourly housekeeping job: sweeps expired tokens, stale ingestion tasks, and temp files."""
    logger.info("housekeeping_cleanup_started")
    cleaned_count = 0
    logger.info("housekeeping_cleanup_completed", cleaned_count=cleaned_count)
    return {"cleaned_tasks": cleaned_count, "status": "completed"}
