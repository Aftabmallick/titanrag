# Runbook RB-05: MinIO S3 Disk Pressure & Orphan Blob Reclamation

## Symptoms
- Alert: `MinIOStorageCapacityHigh` (Disk usage > 85%)
- Document uploads fail with `507 Insufficient Storage` or `IOError`

## Immediate Mitigation
1. Identify large buckets and object volume:
   ```bash
   mc du titan-minio/titan-documents
   mc du titan-minio/titan-wal-archive
   ```
2. Trigger the State Reconciliation Engine:
   ```bash
   python3 -c "from titan_workers.outbox.reconciler import reconcile_vector_storage; reconcile_vector_storage()"
   ```
   Sweeps orphaned blobs in MinIO that have no matching active row in PostgreSQL `documents`.
3. Prune WAL archives older than 7 days:
   ```bash
   mc rm --recursive --force --older-than 7d titan-minio/titan-wal-archive/
   ```
