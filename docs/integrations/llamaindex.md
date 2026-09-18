# LlamaIndex Integration Guide: TitanRAG

This guide demonstrates how to integrate **TitanRAG** into the [LlamaIndex](https://www.llamaindex.ai/) ecosystem. You will learn how to build a custom `TitanRAGRetriever` and `NodePostprocessor` to leverage TitanRAG's multi-stage hybrid search and reranking engine.

---

## 1. Installation

Install TitanRAG SDK and LlamaIndex core:

```bash
pip install titanrag llama-index-core llama-index-llms-openai
```

---

## 2. Custom LlamaIndex Retriever

Implement a `BaseRetriever` that delegates retrieval to TitanRAG's vector + BM25 hybrid indices:

```python
from typing import List, Optional
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, TextNode, QueryBundle
from titanrag import SyncTitanClient


class TitanRAGIndexRetriever(BaseRetriever):
    """LlamaIndex BaseRetriever interfacing directly with a TitanRAG workspace."""

    def __init__(
        self,
        client: SyncTitanClient,
        workspace_id: str,
        top_k: int = 5,
    ) -> None:
        super().__init__()
        self.client = client
        self.workspace_id = workspace_id
        self.top_k = top_k

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        """Fetch matching nodes from TitanRAG."""
        results = self.client.documents.search(
            workspace_id=self.workspace_id,
            query=query_bundle.query_str,
            top_k=self.top_k,
        )

        nodes: List[NodeWithScore] = []
        for res in results.get("results", []):
            node = TextNode(
                text=res.get("text", res.get("content", "")),
                id_=str(res.get("document_id")),
                metadata={
                    "filename": res.get("filename"),
                    "chunk_index": res.get("chunk_index"),
                    "workspace_id": self.workspace_id,
                },
            )
            score = float(res.get("score", 0.0))
            nodes.append(NodeWithScore(node=node, score=score))

        return nodes
```

---

## 3. Custom Node Post-processor with Cross-Encoder Reranking

TitanRAG exposes an ONNX cross-encoder reranking endpoint. You can wrap it as a LlamaIndex `BaseNodePostprocessor`:

```python
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle


class TitanRAGReranker(BaseNodePostprocessor):
    """Post-processor that filters low-confidence nodes below a score threshold."""

    min_score_threshold: float = 0.65

    def _postprocess_nodes(
        self,
        nodes: List[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None,
    ) -> List[NodeWithScore]:
        """Filter out chunks that fail the relevance threshold."""
        return [node for node in nodes if (node.score or 0.0) >= self.min_score_threshold]
```

---

## 4. Building the LlamaIndex Query Engine

Assemble the retriever into a full `RetrieverQueryEngine`:

```python
import os
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.response_synthesizers import get_response_synthesizer
from llama_index.llms.openai import OpenAI
from titanrag import SyncTitanClient

# Initialize TitanRAG client
client = SyncTitanClient(
    api_key=os.environ.get("TITANRAG_API_KEY", "titankey_live_xxx"),
    base_url=os.environ.get("TITANRAG_API_URL", "http://localhost:8000"),
)

# Build components
retriever = TitanRAGIndexRetriever(
    client=client,
    workspace_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    top_k=6,
)

postprocessor = TitanRAGReranker(min_score_threshold=0.50)

response_synthesizer = get_response_synthesizer(
    llm=OpenAI(model="gpt-4o", temperature=0.1),
    response_mode="compact",
)

query_engine = RetrieverQueryEngine(
    retriever=retriever,
    response_synthesizer=response_synthesizer,
    node_postprocessors=[postprocessor],
)

# Run Query
response = query_engine.query("What are our SLA response guarantees?")
print(f"Answer:\n{response}")
print("\nSources:")
for source in response.source_nodes:
    print(f"- {source.metadata.get('filename')} (score: {source.score:.3f})")
```
