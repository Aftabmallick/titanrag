# TitanRAG Enterprise — Disaster Recovery & Business Continuity Runbook

## 1. Executive Summary & Recovery SLAs

TitanRAG enforces strict Recovery Point Objectives (RPO) and Recovery Time Objectives (RTO) across all persistent tiers:

| Tier | Technology | RPO Target | RTO Target | Redundancy Architecture |
|------|------------|------------|------------|-------------------------|
| **Relational Data** | PostgreSQL 16 | **< 1 Hour** | **< 4 Hours** | Nightly base backups + Continuous WAL archiving to S3/MinIO |
| **Vector Storage** | Qdrant 1.12 | **< 1 Hour** | **< 2 Hours** | Hourly / daily collections snapshots shipped to S3/MinIO |
| **Object Blobs** | MinIO / S3 | **< 15 Minutes** | **< 1 Hour** | Erasure coding (4+2 parity) + Cross-Region Active-Passive Sync |
| **State & Cache** | Redis 7 | **Zero Loss** | **< 15 Minutes** | Append-Only File (`appendonly yes`) + Snapshot RDB persistence |

---

## 2. PostgreSQL Point-in-Time Recovery (PITR) Procedure

### 2.1 Restoring Base Backup
1. Stop the active PostgreSQL service:
   ```bash
   docker compose stop postgres
   ```
2. Empty or move the damaged PostgreSQL data directory:
   ```bash
   mv /var/lib/postgresql/data /var/lib/postgresql/data_corrupted_$(date +%s)
   mkdir -p /var/lib/postgresql/data && chmod 700 /var/lib/postgresql/data
   ```
3. Pull the latest base backup tarball from S3/MinIO:
   ```bash
   mc cp titan-minio/titan-backups/latest_basebackup.tar.gz /tmp/basebackup.tar.gz
   tar -xzf /tmp/basebackup.tar.gz -C /var/lib/postgresql/data
   ```

### 2.2 Replaying WAL Archives to Target Timestamp
1. Create a `recovery.signal` trigger file in the data directory:
   ```bash
   touch /var/lib/postgresql/data/recovery.signal
   ```
2. Configure `postgresql.conf` with restoration parameters:
   ```ini
   restore_command = '/packages/infra/scripts/wal_backup.sh restore %f "%p"'
   recovery_target_time = '2026-09-19 18:30:00 UTC'
   recovery_target_action = 'promote'
   ```
3. Start PostgreSQL and monitor the log stream:
   ```bash
   docker compose start postgres
   docker compose logs -f postgres
   ```
4. Confirm PostgreSQL has replayed WAL segments up to target timestamp and promoted to read-write mode.

---

## 3. Qdrant Vector Collection Snapshot Restoration

### 3.1 Fetching Snapshot Archive
```bash
python scripts/qdrant_snapshot.py --url http://localhost:6333 --keep 7
```

### 3.2 Restoring Collection from Snapshot File
To restore a damaged or deleted collection directly from a snapshot:
```bash
curl -X POST "http://localhost:6333/collections/titan_chunks/snapshots/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "snapshot=@/tmp/titan_chunks_snapshot.snapshot"
```

### 3.3 Verifying Collection Health & Point Parity
```bash
curl -s "http://localhost:6333/collections/titan_chunks" | jq .result.status
# Expected: "green"
```

---

## 4. MinIO Object Storage Restoration

1. Verify bucket parity using MinIO Client (`mc`):
   ```bash
   mc mirror --overwrite titan-minio-replica/titan-documents titan-minio/titan-documents
   ```
2. Validate object hashes against PostgreSQL `documents` table checksums (`content_hash_sha256`).

---

## 5. Automated Quarterly DR Drill

Run the automated DR drill script to verify end-to-end recovery readiness:
```bash
python scripts/verify_disaster_recovery.py
```
Outputs cryptographic certification of compliance with SOC 2 Type II and HIPAA disaster recovery mandates.
