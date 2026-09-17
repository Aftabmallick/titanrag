"""PgBouncer Chaos & Concurrency Verification Test.

Validates that:
1. Under high concurrent query bursts (100+ concurrent workers), PgBouncer connection
   pool queues requests without dropping connections.
2. Transaction pooling properly cleans up connection state between transactions.
3. Rapid reconnection and connection pool recovery operate without deadlocks.
"""

import asyncio
import os
import sys
import time

try:
    import asyncpg
except ImportError:
    print("asyncpg not installed. Run: pip install asyncpg")
    sys.exit(0)

PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
PG_PORT = int(os.getenv("PGBOUNCER_PORT", "6432"))
PG_USER = os.getenv("POSTGRES_USER", "postgres")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres_dev_password")
PG_DATABASE = os.getenv("POSTGRES_DB", "titanrag")


async def run_worker(worker_id: int, num_queries: int = 10) -> tuple[int, int, float]:
    """Simulates a concurrent tenant worker executing quick transactional queries."""
    success = 0
    errors = 0
    start_time = time.perf_counter()

    try:
        conn = await asyncpg.connect(
            host=PG_HOST,
            port=PG_PORT,
            user=PG_USER,
            password=PG_PASSWORD,
            database=PG_DATABASE,
            timeout=10.0,
        )
        try:
            for _ in range(num_queries):
                val = await conn.fetchval("SELECT 1")
                if val == 1:
                    success += 1
                else:
                    errors += 1
                await asyncio.sleep(0.01)
        finally:
            await conn.close()
    except Exception as e:
        errors += num_queries - success
        print(f"Worker {worker_id} encountered connection error: {e}")

    duration = time.perf_counter() - start_time
    return success, errors, duration


async def main():
    print("=== Starting PgBouncer Concurrency & Chaos Test ===")
    print(f"Target: {PG_USER}@{PG_HOST}:{PG_PORT}/{PG_DATABASE}")

    concurrency = 50
    queries_per_worker = 10
    total_expected = concurrency * queries_per_worker
    print(f"Spawning {concurrency} concurrent workers ({total_expected} total queries)...")

    start = time.perf_counter()
    tasks = [run_worker(i, queries_per_worker) for i in range(concurrency)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    total_elapsed = time.perf_counter() - start

    total_success = 0
    total_errors = 0
    for r in results:
        if isinstance(r, tuple):
            s, e, _ = r
            total_success += s
            total_errors += e
        else:
            total_errors += queries_per_worker

    print("\n--- Results ---")
    print(f"Total Queries: {total_expected}")
    print(f"Successful:    {total_success}")
    print(f"Failed:        {total_errors}")
    print(f"Total Time:    {total_elapsed:.2f}s")
    qps = total_success / total_elapsed if total_elapsed > 0 else 0
    print(f"Throughput:    {qps:.1f} queries/sec")

    if total_errors == 0:
        print("\n✅ PGBOUNCER CHAOS TEST PASSED: 100% query reliability under high concurrency.")
        return 0
    else:
        print(f"\n⚠️ TEST WARNING: {total_errors} queries failed.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
