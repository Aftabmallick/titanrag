#!/bin/sh
set -e

echo "Initializing MinIO bucket..."
/usr/bin/mc alias set local http://minio:9000 minioadmin minioadmin
/usr/bin/mc mb --ignore-existing local/titanrag-documents
/usr/bin/mc anonymous set download local/titanrag-documents/public || true
echo "MinIO bucket initialized."
