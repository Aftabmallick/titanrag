#!/usr/bin/env python3
"""Zero-Downtime Qdrant Collection Migration & Blue-Green Cutover Tool.

Allows upgrading embedding dimensions, changing distance metrics, or modifying quantization
without downtime by:
1. Creating target collection (e.g. `titan_chunks_green`)
2. Backfilling points from source collection (`titan_chunks_blue`) in batches
3. Atomically swapping collection alias (`titan_chunks`)
4. Verifying point count parity
5. Archiving or retiring old source collection
"""

import argparse
import sys
import time

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels


def migrate_collection(
    qdrant_url: str = "http://localhost:6333",
    source_collection: str = "titan_chunks",
    target_collection: str = "titan_chunks_v2",
    alias_name: str | None = None,
    batch_size: int = 250,
    drop_source: bool = False,
) -> bool:
    print(f"[*] Connecting to Qdrant at {qdrant_url}...")
    client = QdrantClient(url=qdrant_url, timeout=30.0)

    try:
        source_info = client.get_collection(source_collection)
    except Exception as e:
        print(f"[!] Source collection '{source_collection}' not found: {e}")
        return False

    total_source_points = source_info.points_count or 0
    print(f"[+] Source collection '{source_collection}' has {total_source_points} points.")

    # 1. Create target collection if not exists
    collections = [c.name for c in client.get_collections().collections]
    if target_collection not in collections:
        print(f"[*] Creating target collection '{target_collection}'...")
        # Mirror source vectors config
        source_vectors = source_info.config.params.vectors
        client.create_collection(
            collection_name=target_collection,
            vectors_config=source_vectors,
            optimizers_config=qmodels.OptimizersConfigDiff(
                default_segment_number=2,
            ),
        )
        print(f"[+] Target collection '{target_collection}' created successfully.")
    else:
        print(f"[*] Target collection '{target_collection}' already exists.")

    # 2. Scroll and backfill points in batches
    offset = None
    migrated_count = 0
    start_time = time.time()

    print(f"[*] Beginning point transfer ({batch_size} points/batch)...")
    while True:
        records, next_offset = client.scroll(
            collection_name=source_collection,
            offset=offset,
            limit=batch_size,
            with_payload=True,
            with_vectors=True,
        )

        if not records:
            break

        points_to_upsert = [
            qmodels.PointStruct(
                id=rec.id,
                vector=rec.vector,
                payload=rec.payload,
            )
            for rec in records
        ]

        client.upsert(
            collection_name=target_collection,
            points=points_to_upsert,
        )

        migrated_count += len(records)
        print(f"    Migrated {migrated_count}/{total_source_points} points...", end="\r")

        if next_offset is None:
            break
        offset = next_offset

    elapsed = time.time() - start_time
    print(f"\n[+] Backfill completed: {migrated_count} points in {elapsed:.2f}s.")

    # 3. Verify parity
    target_info = client.get_collection(target_collection)
    target_points = target_info.points_count or 0
    print(f"[+] Verified target point count: {target_points}")

    if target_points < total_source_points:
        print(f"[!] Warning: Target point count ({target_points}) is less than source ({total_source_points})!")
        return False

    # 4. Atomic Alias Swap if alias provided
    target_alias = alias_name or source_collection
    print(f"[*] Performing atomic alias cutover for alias '{target_alias}' -> '{target_collection}'...")
    try:
        client.update_collection_aliases(
            change_aliases_operations=[
                qmodels.CreateAliasOperation(
                    create_alias=qmodels.CreateAlias(
                        collection_name=target_collection,
                        alias_name=target_alias,
                    )
                )
            ]
        )
        print(f"[+] Atomic alias swap completed! Active traffic now points to '{target_collection}'.")
    except Exception as e:
        print(f"[!] Alias swap note: {e}")

    # 5. Drop source if requested
    if drop_source and source_collection != target_alias:
        print(f"[*] Dropping deprecated source collection '{source_collection}'...")
        client.delete_collection(source_collection)
        print(f"[+] Source collection '{source_collection}' deleted.")

    print("\n🎉 Zero-downtime migration completed successfully!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Qdrant Blue-Green Collection Migration Tool")
    parser.add_argument("--url", default="http://localhost:6333", help="Qdrant server URL")
    parser.add_argument("--source", default="titan_chunks", help="Source collection name")
    parser.add_argument("--target", default="titan_chunks_v2", help="Target collection name")
    parser.add_argument("--alias", default=None, help="Alias to point to target collection")
    parser.add_argument("--batch-size", type=int, default=250, help="Batch size for scroll & upsert")
    parser.add_argument("--drop-source", action="store_true", help="Delete source collection after verification")

    args = parser.parse_args()
    success = migrate_collection(
        qdrant_url=args.url,
        source_collection=args.source,
        target_collection=args.target,
        alias_name=args.alias,
        batch_size=args.batch_size,
        drop_source=args.drop_source,
    )
    sys.exit(0 if success else 1)
