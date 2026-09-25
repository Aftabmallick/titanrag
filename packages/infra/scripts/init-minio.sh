#!/bin/sh
set -e

echo "Initializing MinIO bucket..."
/usr/bin/mc alias set local http://minio:9000 minioadmin minioadmin
/usr/bin/mc mb --ignore-existing local/titanrag-documents
/usr/bin/mc mb --ignore-existing local/titan-documents-us-east
/usr/bin/mc mb --ignore-existing local/titan-documents-us-west
/usr/bin/mc mb --ignore-existing local/titan-documents-eu-central
/usr/bin/mc mb --ignore-existing local/titan-documents-eu-west
/usr/bin/mc mb --ignore-existing local/titan-documents-apac-se
/usr/bin/mc anonymous set download local/titanrag-documents/public || true
echo "MinIO buckets initialized."
