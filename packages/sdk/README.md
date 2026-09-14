# TitanRAG Python SDK & CLI

Official client library and developer CLI for TitanRAG Enterprise Platform.

## Quick Installation
```bash
pip install titanrag
```

## Basic Usage
```python
import asyncio
from titanrag import TitanRAGClient


async def main():
    client = TitanRAGClient(base_url="http://localhost:8000/api/v1", api_key="rg_...")
    health = await client.get_health()
    print(health)


asyncio.run(main())
```
