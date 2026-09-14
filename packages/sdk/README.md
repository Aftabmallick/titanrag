# TitanRAG Python SDK & CLI

Official Python client library for the TitanRAG Enterprise Platform.

## Installation

```bash
pip install titanrag
```

## Usage

### Basic Async Context Manager

```python
import asyncio
from titanrag import TitanRAGClient, TitanRAGError


async def main():
    async with TitanRAGClient(base_url="http://localhost:8000/api/v1", api_key="rg_test_key") as client:
        # Check system liveness
        liveness = await client.get_health_live()
        print("Liveness:", liveness)

        # Query deep readiness probe (PostgreSQL, Qdrant, Redis, MinIO)
        try:
            readiness = await client.get_health_ready()
            print("Readiness:", readiness)
        except TitanRAGError as err:
            print(f"System degraded: {err.message} (status: {err.status_code})")

        # Fetch Prometheus metrics
        metrics = await client.get_metrics()
        print("Metrics size:", len(metrics))


if __name__ == "__main__":
    asyncio.run(main())
```
