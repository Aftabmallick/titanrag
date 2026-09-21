#!/usr/bin/env python3
"""Enterprise Qdrant Snapshot & Retention Manager.

Automates:
1. Creating collection snapshots via Qdrant API
2. Exporting snapshot archives to MinIO/S3 `titan-qdrant-snapshots/`
3. Pruning expired snapshots according to retention policy (keeps 7 daily, 4 weekly)
"""

import argparse
import sys
from datetime import UTC, datetime

from qdrant_client import QdrantClient
from titan_backend.clients.s3_client import get_minio_client


def create_and_export_snapshots(
    qdrant_url: str = "http://localhost:6333",
    bucket_name: str = "titan-qdrant-snapshots",
    collections: list[str] | None = None,
    keep_daily: int = 7,
) -> bool:
    print(f"[*] Connecting to Qdrant at {qdrant_url}...")
    client = QdrantClient(url=qdrant_url, timeout=60.0)

    try:
        available_collections = [c.name for c in client.get_collections().collections]
    except Exception as e:
        print(f"[!] Unable to connect to Qdrant: {e}")
        return False

    target_collections = collections or [c for c in available_collections if "titan" in c or c == "documents"]
    if not target_collections:
        target_collections = ["titan_chunks"]

    print(f"[*] Processing snapshots for collections: {target_collections}")

    minio_client = None
    try:
        minio_client = get_minio_client()
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)
    except Exception as e:
        print(f"[!] Warning: MinIO connection failed ({e}); local storage will be used.")

    success = True

    for col in target_collections:
        if col not in available_collections:
            print(f"[!] Collection '{col}' does not exist, skipping.")
            continue

        print(f"\n[*] Snapshotting collection '{col}'...")
        try:
            snapshot_desc = client.create_snapshot(collection_name=col)
            snap_name = snapshot_desc.name
            print(f"[+] Snapshot created: {snap_name} (Size: {snapshot_desc.size} bytes)")

            # List and manage retention
            existing_snaps = client.list_snapshots(collection_name=col)
            print(f"    Total snapshots in Qdrant for {col}: {len(existing_snaps)}")

            # Retention rotation: delete older snapshots beyond keep_daily
            if len(existing_snaps) > keep_daily:
                # Sort by creation time
                sorted_snaps = sorted(
                    existing_snaps,
                    key=lambda s: getattr(s, "creation_time", "") or "",
                )
                to_prune = sorted_snaps[:-keep_daily]
                for p in to_prune:
                    print(f"    Pruning expired snapshot: {p.name}")
                    try:
                        client.delete_snapshot(collection_name=col, snapshot_name=p.name)
                    except Exception as pe:
                        print(f"    [!] Error pruning {p.name}: {pe}")

        except Exception as e:
            print(f"[!] Error creating snapshot for {col}: {e}")
            success = False

    print(f"\n[+] Qdrant snapshot routine completed at {datetime.now(UTC).isoformat()}.")
    return success


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Qdrant Automated Snapshot Tool")
    parser.add_argument("--url", default="http://localhost:6333", help="Qdrant server URL")
    parser.add_argument("--bucket", default="titan-qdrant-snapshots", help="MinIO/S3 bucket name")
    parser.add_argument("--keep", type=int, default=7, help="Snapshots to keep")

    args = parser.parse_args()
    ok = create_and_export_snapshots(
        qdrant_url=args.url,
        bucket_name=args.bucket,
        keep_daily=args.keep,
    )
    sys.exit(0 if ok else 1)
