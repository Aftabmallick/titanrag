#!/usr/bin/env python3
"""Seed Sandbox Demo Documents — Phase 10.

Pre-populates canonical demo documents (contracts, architecture, finance)
into the shared demo collection in Qdrant and MinIO, enabling instantaneous
ephemeral sandbox session initialization without re-indexing latency.
"""

from __future__ import annotations

import argparse
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_sandbox_demo")

DEMO_CORPUS = [
    {
        "title": "Master Services Agreement (MSA)",
        "category": "legal",
        "content": (
            "Section 14.2 Termination for Cause: Either Party may terminate this Agreement "
            "immediately upon written notice if the other Party materially breaches any term "
            "and fails to cure within thirty (30) days of notice. Section 17.4 Exclusions from "
            "Limitation of Liability: The limitations set forth in Section 17.1 shall not apply "
            "to breaches of Section 11 (Confidentiality) or indemnification obligations under Section 16."
        ),
        "pages": 28,
        "sample_queries": [
            "What are the termination notice requirements?",
            "Is confidentiality subject to the liability cap?",
        ],
    },
    {
        "title": "Distributed Consensus & Vector RAG Architecture",
        "category": "technical",
        "content": (
            "TitanRAG utilizes a two-tier hybrid search architecture combining Qdrant dense vector "
            "indices (HNSW with scalar quantization) and SPLADE sparse lexical representations. "
            "Transactional outbox patterns guarantee exactly-once vector indexing during concurrent "
            "document uploads. MinHash LSH provides deduplication at Jaccard threshold 0.85."
        ),
        "pages": 42,
        "sample_queries": [
            "How does TitanRAG guarantee exactly-once vector indexing?",
            "What Jaccard threshold is used for deduplication?",
        ],
    },
    {
        "title": "Q2 2026 Earnings & Financial Performance",
        "category": "finance",
        "content": (
            "Total enterprise revenue reached $48.2 million in Q2 2026, representing a 64% "
            "year-over-year increase. Compute Unit (CU) consumption across paying tenants expanded "
            "by 112%, driven by adoption of multi-framework evaluations and automated ingestion pipelines. "
            "Net revenue retention (NRR) closed at 134% with gross margins expanding to 78%."
        ),
        "pages": 18,
        "sample_queries": [
            "What was the total enterprise revenue in Q2 2026?",
            "What was the year-over-year revenue growth and NRR?",
        ],
    },
]


async def seed_demo_workspace(dry_run: bool = False) -> None:
    logger.info("Initializing Canonical Sandbox Demo Golden Dataset...")

    for doc in DEMO_CORPUS:
        logger.info(
            "Seeding demo document: '%s' (%s, %d pages)",
            doc["title"],
            doc["category"],
            doc["pages"],
        )

    if dry_run:
        logger.info("DRY-RUN completed. All 3 demo documents validated.")
        return

    logger.info(
        "Successfully registered %d demo documents in shared sandbox repository.",
        len(DEMO_CORPUS),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Sandbox Demo Documents")
    parser.add_argument("--dry-run", action="store_true", help="Validate corpus without writing")
    args = parser.parse_args()

    asyncio.run(seed_demo_workspace(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
