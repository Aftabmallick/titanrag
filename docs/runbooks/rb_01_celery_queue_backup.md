# Runbook RB-01: Celery Queue Backup & Task Starvation Recovery

## Symptoms
- Alert: `CeleryQueueDepthHigh` (Queue depth > 1,000 tasks for > 5 minutes)
- Document ingestion status remains `PROCESSING` for > 30 minutes
- Flower UI (`http://localhost:5555`) shows pending tasks growing faster than completed rate

## Root Cause Diagnosis
1. Check queue depth per priority tier:
   ```bash
   docker exec -it titan-redis redis-cli LLEN p0_interactive
   docker exec -it titan-redis redis-cli LLEN p1_default
   docker exec -it titan-redis redis-cli LLEN p2_bulk_sync
   ```
2. Inspect worker child processes for hung Docling / OCR / PyTorch jobs:
   ```bash
   docker top titan-celery-heavy
   ```
3. Check worker container memory usage for near-OOM thrashing:
   ```bash
   docker stats titan-celery-core titan-celery-heavy
   ```

## Immediate Mitigation
1. Scale up celery core workers immediately:
   ```bash
   docker compose up -d --scale celery-worker=4
   # On Kubernetes:
   kubectl scale deployment titanrag-workers-core --replicas=8
   ```
2. Purge or drain low-priority bulk sync jobs if blocking interactive uploads:
   ```bash
   # Move p2 tasks to dead-letter queue or pause connector polling
   docker exec -it titan-redis redis-cli RENAME p2_bulk_sync p2_bulk_sync_paused
   ```

## Dead-Letter Queue (DLQ) Recovery
Inspect failed tasks and retry eligible jobs:
```bash
curl -X GET "http://localhost:8000/api/v1/dlq/tasks?status=FAILED" \
  -H "Authorization: Bearer <ADMIN_TOKEN>"

# Replay specific failed task
curl -X POST "http://localhost:8000/api/v1/dlq/tasks/<TASK_ID>/retry" \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

## Prevention
- Enforce `--max-memory-per-child=1048576` (reaps worker after 1GB)
- Enforce `--prefetch-multiplier=1`
- Configure Kubernetes Horizontal Pod Autoscaler based on queue depth metrics from Prometheus.
