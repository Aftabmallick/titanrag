# LangChain Integration Guide: TitanRAG

This guide demonstrates how to integrate **TitanRAG** with [LangChain](https://www.langchain.com/) using the official `titanrag` Python SDK. You will learn how to build a custom `TitanRAGRetriever` and wrap TitanRAG's streaming chat engine as a LangChain `Runnable`.

---

## 1. Installation

Install the TitanRAG SDK and LangChain:

```bash
pip install titanrag langchain-core langchain-openai
```

---

## 2. Custom `TitanRAGRetriever`

The following retriever queries a TitanRAG workspace, maps the retrieved document chunks into LangChain `Document` objects, and attaches citation metadata (source file, similarity score, chunk index).

```python
from typing import Any, List, Optional
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import Field

from titanrag import SyncTitanClient


class TitanRAGRetriever(BaseRetriever):
    """LangChain BaseRetriever backed by a TitanRAG enterprise workspace."""

    client: SyncTitanClient = Field(description="TitanRAG SDK synchronous client")
    workspace_id: str = Field(description="Target TitanRAG Workspace UUID")
    top_k: int = Field(default=5, description="Number of relevant chunks to retrieve")

    class Config:
        arbitrary_types_allowed = True

    def _get_relevant_documents(
        self, query: str, *, run_manager: Optional[CallbackManagerForRetrieverRun] = None
    ) -> List[Document]:
        """Perform semantic retrieval against TitanRAG."""
        # Query TitanRAG search endpoint
        search_results = self.client.documents.search(
            workspace_id=self.workspace_id,
            query=query,
            top_k=self.top_k,
        )

        documents: List[Document] = []
        for item in search_results.get("results", []):
            doc = Document(
                page_content=item.get("text", item.get("content", "")),
                metadata={
                    "document_id": item.get("document_id"),
                    "filename": item.get("filename"),
                    "score": item.get("score"),
                    "chunk_index": item.get("chunk_index"),
                    "workspace_id": self.workspace_id,
                },
            )
            documents.append(doc)

        return documents


# --- Example Usage ---
if __name__ == "__main__":
    client = SyncTitanClient(api_key="titankey_live_xxxxxxxxxxxx")
    retriever = TitanRAGRetriever(
        client=client,
        workspace_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        top_k=3,
    )

    docs = retriever.invoke("What are our Q3 financial performance drivers?")
    for i, doc in enumerate(docs, 1):
        print(f"[{i}] {doc.metadata['filename']} (Score: {doc.metadata['score']:.3f})")
        print(f"    {doc.page_content[:120]}...\n")
```

---

## 3. LangChain LCEL RAG Pipeline

Combine `TitanRAGRetriever` with LangChain Expression Language (LCEL) and OpenAI:

```python
import os
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI
from titanrag import SyncTitanClient

# 1. Initialize Clients
titan_client = SyncTitanClient(api_key=os.environ["TITANRAG_API_KEY"])
retriever = TitanRAGRetriever(
    client=titan_client,
    workspace_id=os.environ["TITANRAG_WORKSPACE_ID"],
    top_k=4,
)
llm = ChatOpenAI(model="gpt-4o", temperature=0.1)

# 2. Format documents helper
def format_docs(docs):
    return "\n\n".join(
        f"[Source: {d.metadata.get('filename')}]\n{d.page_content}"
        for d in docs
    )

# 3. Prompt Template
template = """Answer the query using exclusively the provided context. If unknown, state that you do not know.

Context:
{context}

Question: {question}
Answer:"""

prompt = ChatPromptTemplate.from_template(template)

# 4. Chain Definition
rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

# 5. Execution
response = rag_chain.invoke("What are our data retention guidelines?")
print(response)
```

---

## 4. Native TitanRAG Chat Streaming with LangChain Callbacks

If you want to use TitanRAG's built-in hybrid re-ranking and citation engine directly while dispatching LangChain streaming callbacks:

```python
from titanrag import SyncTitanClient
from langchain_core.callbacks import StreamingStdOutCallbackHandler

client = SyncTitanClient(api_key="titankey_live_xxxxxxxxxxxx")
handler = StreamingStdOutCallbackHandler()

for chunk in client.chat.stream(
    workspace_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    message="Summarize the SOC 2 audit report",
):
    if chunk.type == "token":
        handler.on_llm_new_token(chunk.content)
    elif chunk.type == "citation":
        print(f"\n[Citation: {chunk.title} - Score: {chunk.score}]")
```
