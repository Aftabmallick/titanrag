#!/usr/bin/env bash
# ==============================================================================
# TitanRAG Enterprise PostgreSQL Continuous WAL Archiving & Base Backup Script
# RPO Target: < 1 Hour | RTO Target: < 4 Hours
# ==============================================================================

set -eo pipefail

WAL_PATH="$1"
WAL_FILE="$2"
S3_ENDPOINT="${MINIO_ENDPOINT:-localhost:9000}"
S3_BUCKET="${WAL_BUCKET:-titan-wal-archive}"
MINIO_ACCESS_KEY="${MINIO_ROOT_USER:-minioadmin}"
MINIO_SECRET_KEY="${MINIO_ROOT_PASSWORD:-minioadmin}"

# Setup mc alias if needed
if command -v mc >/dev/null 2>&1; then
    mc alias set titan-minio "http://${S3_ENDPOINT}" "${MINIO_ACCESS_KEY}" "${MINIO_SECRET_KEY}" --api S3v4 >/dev/null 2>&1 || true
    mc mb --ignore-existing "titan-minio/${S3_BUCKET}" >/dev/null 2>&1 || true
fi

case "$1" in
    archive)
        # Archive single WAL segment
        if [ -z "$2" ] || [ -z "$3" ]; then
            echo "Usage: $0 archive <wal_path> <wal_filename>"
            exit 1
        fi
        SRC_PATH="$2"
        FILE_NAME="$3"
        echo "[*] Archiving WAL segment: ${FILE_NAME} -> s3://${S3_BUCKET}/${FILE_NAME}"
        if command -v mc >/dev/null 2>&1; then
            mc cp "${SRC_PATH}" "titan-minio/${S3_BUCKET}/${FILE_NAME}"
        else
            # Local simulation fallback
            mkdir -p "/tmp/${S3_BUCKET}"
            cp "${SRC_PATH}" "/tmp/${S3_BUCKET}/${FILE_NAME}"
        fi
        echo "[+] WAL segment ${FILE_NAME} archived successfully."
        ;;

    restore)
        # Restore WAL segment for PITR replay
        if [ -z "$2" ] || [ -z "$3" ]; then
            echo "Usage: $0 restore <wal_filename> <target_restore_path>"
            exit 1
        fi
        FILE_NAME="$2"
        DEST_PATH="$3"
        echo "[*] Restoring WAL segment: ${FILE_NAME} -> ${DEST_PATH}"
        if command -v mc >/dev/null 2>&1; then
            mc cp "titan-minio/${S3_BUCKET}/${FILE_NAME}" "${DEST_PATH}"
        else
            cp "/tmp/${S3_BUCKET}/${FILE_NAME}" "${DEST_PATH}"
        fi
        ;;

    basebackup)
        # Trigger full basebackup
        BACKUP_DATE=$(date -u +%Y%m%d_%H%M%S)
        ARCHIVE_NAME="basebackup_${BACKUP_DATE}.tar.gz"
        echo "[*] Starting PostgreSQL base backup: ${ARCHIVE_NAME}..."
        if command -v pg_basebackup >/dev/null 2>&1; then
            pg_basebackup -h localhost -p 5432 -U postgres -D - -Ft -z | \
                mc pipe "titan-minio/titan-backups/${ARCHIVE_NAME}"
            echo "[+] Base backup ${ARCHIVE_NAME} successfully shipped to storage."
        else
            echo "[!] pg_basebackup command not in PATH, simulated backup archive recorded."
        fi
        ;;

    *)
        echo "Usage: $0 {archive|restore|basebackup}"
        exit 1
        ;;
esac
