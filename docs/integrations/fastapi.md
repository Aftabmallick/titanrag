# FastAPI Microservice Integration: TitanRAG

This guide demonstrates how to integrate the asynchronous `AsyncTitanClient` into a separate FastAPI microservice using best-practice dependency injection and lifespan connection management.

---

## 1. Installation

```bash
pip install titanrag fastapi uvicorn pydantic
```

---

## 2. Lifespan Client Injection (`dependencies.py`)

Using a single shared `AsyncTitanClient` instance across your FastAPI application ensures connection reuse and pooled HTTP keep-alive connections.

```python
# dependencies.py
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Depends, Request
import os
from titanrag import AsyncTitanClient


class TitanClientManager:
    client: AsyncTitanClient | None = None

    @classmethod
    def get_client(cls) -> AsyncTitanClient:
        if cls.client is None:
            raise RuntimeError("TitanClientManager not initialized")
        return cls.client


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize client pool
    api_key = os.environ.get("TITANRAG_API_KEY", "titankey_live_secret")
    base_url = os.environ.get("TITANRAG_API_URL", "http://localhost:8000")

    TitanClientManager.client = AsyncTitanClient(
        api_key=api_key,
        base_url=base_url,
        timeout=60.0,
        max_retries=3,
    )
    yield
    # Shutdown: Close client session gracefully
    if TitanClientManager.client:
        await TitanClientManager.client.close()


def get_titan_client() -> AsyncTitanClient:
    """FastAPI Dependency for route handlers."""
    return TitanClientManager.get_client()
```

---

## 3. Microservice Route Handlers (`main.py`)

```python
# main.py
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import os

from dependencies import lifespan, get_titan_client
from titanrag import AsyncTitanClient
from titanrag.exceptions import TitanRAGError, RateLimitError, AuthenticationError

app = FastAPI(title="Internal Corporate AI Service", lifespan=lifespan)
DEFAULT_WORKSPACE_ID = os.environ.get("DEFAULT_WORKSPACE_ID", "a1b2c3d4-e5f6-7890-abcd-ef1234567890")


class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5


class ChatRequest(BaseModel):
    message: str
    workspace_id: Optional[str] = None


@app.post("/internal/search")
async def internal_semantic_search(
    req: QueryRequest,
    client: AsyncTitanClient = Depends(get_titan_client),
):
    """Execute vector & keyword semantic search against company docs."""
    try:
        results = await client.documents.search(
            workspace_id=DEFAULT_WORKSPACE_ID,
            query=req.query,
            top_k=req.top_k or 5,
        )
        return {"count": len(results.get("results", [])), "items": results.get("results", [])}
    except AuthenticationError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid TitanRAG API credentials")
    except RateLimitError:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="TitanRAG rate limit reached")
    except TitanRAGError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"TitanRAG upstream error: {str(e)}")


@app.post("/internal/stream-chat")
async def internal_stream_chat(
    req: ChatRequest,
    client: AsyncTitanClient = Depends(get_titan_client),
):
    """Stream real-time LLM answers with citation metadata to internal consumers."""
    target_workspace = req.workspace_id or DEFAULT_WORKSPACE_ID

    async def event_generator():
        try:
            async for chunk in client.chat.stream(
                workspace_id=target_workspace,
                message=req.message,
            ):
                if chunk.type == "token":
                    yield f"data: {chunk.content}\n\n"
                elif chunk.type == "citation":
                    yield f"event: citation\ndata: {chunk.model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"event: error\ndata: {str(e)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```
