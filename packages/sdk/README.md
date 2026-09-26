# TitanRAG Python SDK & CLI

Official Python client library and developer CLI for the [TitanRAG Enterprise Platform](https://github.com/Aftabmallick/titanrag).

[![PyPI](https://img.shields.io/pypi/v/titanrag.svg)](https://pypi.org/project/titanrag/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: BSL-1.1](https://img.shields.io/badge/License-BSL--1.1-orange.svg)](https://github.com/Aftabmallick/titanrag/blob/master/LICENSE)

---

## Installation

```bash
pip install titanrag
```

Or with `uv`:

```bash
uv add titanrag
```

---

## Python SDK Usage

TitanRAG provides both **async** (`AsyncTitanClient` / `TitanRAGClient`) and **synchronous** (`TitanClient`) clients with built-in retries, jitter, and automatic token management.

### 1. Asynchronous Client (Recommended)

```python
import asyncio
from titanrag import AsyncTitanClient, TitanRAGError


async def main():
    async with AsyncTitanClient(
        base_url="http://localhost:8000/api/v1",
        api_key="your_api_key",
    ) as client:
        # Check system readiness
        health = await client.get_health_ready()
        print("TitanRAG Ready:", health)

        # Ask a question across a workspace
        response = await client.ask(
            workspace_id="your-workspace-id",
            question="What is our disaster recovery RTO objective?",
        )
        print("Answer:", response.answer)
        for citation in response.citations:
            print(f"- [{citation.source}] (relevance: {citation.score:.2f})")


if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Streaming Responses (Real-time SSE)

Stream answer tokens, citations, and status events in real time:

```python
import asyncio
from titanrag import AsyncTitanClient


async def main():
    async with AsyncTitanClient(base_url="http://localhost:8000/api/v1", api_key="your_api_key") as client:
        async for event in client.chat_stream(
            workspace_id="your-workspace-id",
            prompt="Summarize the Q3 cloud infrastructure budget.",
        ):
            if event.event_type == "token":
                print(event.data.get("token", ""), end="", flush=True)
            elif event.event_type == "citation":
                print(f"\n[Citation: {event.data.get('document_title')}]")
            elif event.event_type == "done":
                print("\nStream completed.")


if __name__ == "__main__":
    asyncio.run(main())
```

### 3. Synchronous Client

For CLI tools, scripts, or legacy sync environments:

```python
from titanrag import TitanClient

with TitanClient(base_url="http://localhost:8000/api/v1", api_key="your_api_key") as client:
    response = client.ask(
        workspace_id="your-workspace-id",
        question="What are the key security policies for vendor API access?",
    )
    print(response.answer)
```

### 4. Document Ingestion

Upload documents for asynchronous ingestion, chunking, and embedding:

```python
import asyncio
from titanrag import AsyncTitanClient


async def main():
    async with AsyncTitanClient(base_url="http://localhost:8000/api/v1", api_key="your_api_key") as client:
        result = await client.upload_file(
            workspace_id="your-workspace-id",
            file_path="contracts/master_services_agreement.pdf",
        )
        print(f"Document uploaded: {result.document_id}, status: {result.status}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Developer CLI (`titan`)

The package includes the `titan` CLI for terminal productivity, CI/CD pipelines, and script automation.

```bash
# Verify installation
titan version

# Authenticate against your TitanRAG cluster
titan login --url http://localhost:8000/api/v1 --key your_api_key

# Check current active profile
titan whoami

# Query with terminal markdown streaming
titan query "Explain the multi-tenant isolation model" --workspace my-workspace

# Pipe prompts via stdin
cat query.txt | titan query --workspace my-workspace

# Interactive REPL chat session
titan repl --workspace my-workspace

# Upload documents
titan upload path/to/report.pdf --workspace my-workspace
```

---

## Error Handling

TitanRAG provides structured exceptions corresponding to HTTP response codes:

```python
from titanrag import (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ServerError,
    TitanRAGError,
)

try:
    response = client.ask(workspace_id="ws-123", question="Hello")
except AuthenticationError:
    print("Invalid or expired API key.")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds.")
except NotFoundError:
    print("Workspace or document not found.")
except TitanRAGError as e:
    print(f"TitanRAG Error [{e.status_code}]: {e.message}")
```

---

## License

TitanRAG is licensed under the [Business Source License 1.1 (BSL-1.1)](https://github.com/Aftabmallick/titanrag/blob/master/LICENSE).
