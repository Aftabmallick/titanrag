# TitanRAG Workers Service

Celery asynchronous background workers and Transactional Outbox Relay process.
Includes partitioned queues (`p0_interactive`, `p1_default`, `p2_bulk_sync`, `heavy_ml`), task state management, and daily vector reconciler.
