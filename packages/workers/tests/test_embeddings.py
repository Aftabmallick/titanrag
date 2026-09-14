import math

import pytest
from titan_workers.pipeline.embedding.dense_embedder import DenseEmbedder
from titan_workers.pipeline.embedding.sparse_embedder import SparseBM25Embedder, WorkspaceIDFManager


@pytest.mark.asyncio
async def test_dense_embedder_batch():
    embedder = DenseEmbedder(dimension=1536)
    texts = ["First test document chunk.", "Second independent text snippet."]
    vectors = await embedder.embed_batch(texts, batch_size=2)

    assert len(vectors) == 2
    assert len(vectors[0]) == 1536
    assert len(vectors[1]) == 1536

    # Verify unit L2 normalization
    norm0 = math.sqrt(sum(x * x for x in vectors[0]))
    assert abs(norm0 - 1.0) < 1e-4


def test_sparse_bm25_embedder():
    embedder = SparseBM25Embedder(k1=1.5, b=0.75)
    text = "Enterprise RAG system with hybrid search and Qdrant vector indexing."
    sparse_vec = embedder.generate_sparse_vector(text)

    assert "indices" in sparse_vec
    assert "values" in sparse_vec
    assert len(sparse_vec["indices"]) == len(sparse_vec["values"])
    assert len(sparse_vec["indices"]) >= 5

    # All indices must be non-negative 32-bit integers
    for idx in sparse_vec["indices"]:
        assert isinstance(idx, int)
        assert 0 <= idx <= 0x7FFFFFFF

    # All values must be positive floats
    for val in sparse_vec["values"]:
        assert isinstance(val, float)
        assert val > 0.0


def test_sparse_bm25_workspace_idf_weighting():
    idf_mgr = WorkspaceIDFManager()
    ws_id = "ws_test_idf"

    # Record 10 documents where 'contract' appears in 1 doc, and 'general' appears in 10 docs
    for _ in range(9):
        idf_mgr.record_document_terms(ws_id, {"general", "standard"})
    idf_mgr.record_document_terms(ws_id, {"general", "contract"})

    embedder = SparseBM25Embedder(idf_manager=idf_mgr)

    # Compute sparse vector for document containing both 'contract' and 'general'
    test_doc = "general contract"
    vec = embedder.generate_sparse_vector(test_doc, workspace_id=ws_id)

    contract_idx = embedder._hash_token("contract")
    general_idx = embedder._hash_token("general")

    contract_weight = vec["values"][vec["indices"].index(contract_idx)]
    general_weight = vec["values"][vec["indices"].index(general_idx)]

    # Rare term 'contract' must have a significantly higher IDF weight than frequent term 'general'
    assert contract_weight > general_weight
    assert idf_mgr.compute_idf(ws_id, "contract") > idf_mgr.compute_idf(ws_id, "general")
