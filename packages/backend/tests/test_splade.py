from qdrant_client.http import models as qmodels
from titan_backend.retrieval.multi_sparse_fusion import MultiSparseHybridFusion
from titan_backend.retrieval.splade import SpladeSparseEmbedder


def test_splade_sparse_embedder():
    text = "TitanRAG implements advanced retrieval with PostgreSQL and vector search."
    sparse_vec = SpladeSparseEmbedder.embed_text(text)

    assert isinstance(sparse_vec, qmodels.SparseVector)
    assert len(sparse_vec.indices) > 0
    assert len(sparse_vec.values) == len(sparse_vec.indices)
    assert all(isinstance(idx, int) for idx in sparse_vec.indices)
    assert all(val > 0.0 for val in sparse_vec.values)
    # Indices are sorted ascending for Qdrant
    assert sparse_vec.indices == sorted(sparse_vec.indices)


def test_multi_sparse_hybrid_fusion():
    dense_results = [
        {"chunk_id": "chunk_1", "content": "Dense candidate 1"},
        {"chunk_id": "chunk_2", "content": "Dense candidate 2"},
    ]
    bm25_results = [
        {"chunk_id": "chunk_2", "content": "BM25 candidate 2"},
        {"chunk_id": "chunk_3", "content": "BM25 candidate 3"},
    ]
    splade_results = [
        {"chunk_id": "chunk_2", "content": "SPLADE candidate 2"},
        {"chunk_id": "chunk_1", "content": "SPLADE candidate 1"},
    ]

    fused = MultiSparseHybridFusion.fuse_rankings(
        dense_results=dense_results,
        bm25_results=bm25_results,
        splade_results=splade_results,
        alpha=1.0,
        beta=0.5,
        gamma=0.8,
        top_n=3,
    )

    assert len(fused) == 3
    # chunk_2 appeared in all 3 lists (rank 2 in dense, rank 1 in bm25, rank 1 in splade), so it should rank first
    assert fused[0]["chunk_id"] == "chunk_2"
    assert fused[0]["fused_rank"] == 1
    assert fused[0]["fused_score"] > fused[1]["fused_score"]
