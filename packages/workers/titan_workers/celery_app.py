import os

from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue

REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery(
    "titan_workers",
    broker=REDIS_URL,
    backend=RESULT_BACKEND,
    include=[
        "titan_workers.tasks.housekeeping",
        "titan_workers.tasks.ingestion",
        "titan_workers.tasks.deep_research",
        "titan_workers.tasks.nli_guardrail",
        "titan_workers.outbox.reconciler",
    ],
)

# Queues & Routing Topology
default_exchange = Exchange("titan_tasks", type="direct")
celery_app.conf.task_queues = [
    Queue("p0_interactive", default_exchange, routing_key="p0_interactive"),
    Queue("p1_default", default_exchange, routing_key="p1_default"),
    Queue("p2_bulk_sync", default_exchange, routing_key="p2_bulk_sync"),
    Queue("heavy_ml", default_exchange, routing_key="heavy_ml"),
    Queue("reranking", default_exchange, routing_key="reranking"),
]
celery_app.conf.task_default_queue = "p1_default"
celery_app.conf.task_default_exchange = "titan_tasks"
celery_app.conf.task_default_routing_key = "p1_default"

# Hardened Worker Configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,  # Prevent prefetching bottlenecks on long OCR/chunk tasks
    worker_max_memory_per_child=1048576,  # Auto-reap child after 1GB RAM to eliminate ML memory leaks
    task_acks_late=True,  # Acknowledge only after task completes
    task_reject_on_worker_lost=True,  # Re-queue task if worker crashes
    broker_connection_retry_on_startup=True,
)

# Celery Beat Periodic Schedule
celery_app.conf.beat_schedule = {
    "daily-vector-reconciler": {
        "task": "titan_workers.outbox.reconciler.reconcile_vector_storage",
        "schedule": crontab(hour=2, minute=0),  # Daily at 02:00 UTC
    },
    "hourly-stale-cleanup": {
        "task": "titan_workers.tasks.housekeeping.cleanup_stale_tasks",
        "schedule": crontab(minute=30),  # Hourly at :30
    },
    "daily-staleness-check": {
        "task": "titan_workers.tasks.housekeeping.check_document_staleness",
        "schedule": crontab(hour=4, minute=0),  # Daily at 04:00 UTC
    },
}
