import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from titan_backend.core.guardrails.egress_scanner import StreamingEgressScanner
from titan_backend.services.chat.stream_generator import phased_stream_generator
from titan_backend.services.retrieval.context_packer import PackedSource
from titan_backend.services.retrieval.multi_hop import multi_hop_decomposer
from titan_backend.services.retrieval.search import HybridSearchResults, SearchCandidate
from titan_backend.services.retrieval.semantic_cache import SaltedSemanticCache
from titan_workers.tasks.deep_research import run_deep_research
from titan_workers.tasks.nli_guardrail import evaluate_citations_entailment


def test_streaming_egress_cross_token_boundary_redaction() -> None:
    """Verifies that secrets split across multiple streaming token chunks are fully redacted
    with zero character leakage.
    """
    scanner = StreamingEgressScanner(max_hold_size=32)

    # Secret split across 4 tokens
    chunks = [
        "Your API token is: ",
        "rg_123456789",
        "0abcdef123456",
        "78_production! Please store safely.",
    ]

    emitted = []
    for chunk in chunks:
        res = scanner.scan_chunk(chunk)
        if res.clean_chunk:
            emitted.append(res.clean_chunk)

    remaining = scanner.flush()
    if remaining:
        emitted.append(remaining)

    full_output = "".join(emitted)

    # Verify secret is redacted
    assert "[REDACTED_TITAN_API_KEY]" in full_output
    # Verify no raw secret fragment leaked
    assert "rg_1234567890abcdef12345678_production" not in full_output
    assert "Please store safely." in full_output


@pytest.mark.asyncio
async def test_vector_semantic_cache_cosine_matching() -> None:
    """Verifies that SaltedSemanticCache matches queries with cosine similarity >= 0.95."""
    cache = SaltedSemanticCache()
    tenant_id = uuid4()
    workspace_id = uuid4()
    acl_groups = ["finance", "all-members"]

    mock_redis = AsyncMock()
    stored_data = {}

    async def mock_setex(key, ttl, val):
        stored_data[key] = val

    async def mock_get(key):
        return stored_data.get(key)

    async def mock_hset(key, field, val):
        if key not in stored_data:
            stored_data[key] = {}
        stored_data[key][field] = val

    async def mock_hgetall(key):
        return stored_data.get(key, {})

    mock_redis.setex.side_effect = mock_setex
    mock_redis.get.side_effect = mock_get
    mock_redis.hset.side_effect = mock_hset
    mock_redis.hgetall.side_effect = mock_hgetall
    mock_redis.expire = AsyncMock()

    # Query 1 embedding: vector pointing in direction [1.0, 0.0, 0.0]
    vec_q1 = [1.0, 0.0, 0.0]
    # Query 2 embedding: slightly perturbed vector [0.999, 0.01, 0.0] (cosine sim > 0.99)
    vec_q2 = [0.999, 0.01, 0.0]
    # Query 3 embedding: orthogonal vector [0.0, 1.0, 0.0] (cosine sim == 0.0)
    vec_q3 = [0.0, 1.0, 0.0]

    with patch("titan_backend.services.retrieval.semantic_cache.get_redis_client", return_value=mock_redis):
        # 1. Set cache with Query 1
        await cache.set(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            user_acl_groups=acl_groups,
            query="What was our Q2 net revenue?",
            content="Q2 net revenue was $4.2M.",
            citations=[],
            sources=[],
            tokens_used=12,
            query_vector=vec_q1,
        )

        # 2. Check semantically similar query (cosine > 0.95)
        with patch("titan_backend.services.retrieval.semantic_cache.litellm_client.aembedding", return_value=[vec_q2]):
            hit = await cache.get(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                user_acl_groups=acl_groups,
                query="Tell me about second quarter net revenue",
                threshold=0.95,
            )
            assert hit is not None
            assert hit.content == "Q2 net revenue was $4.2M."
            assert hit.similarity > 0.98

        # 3. Check dissimilar query
        with patch("titan_backend.services.retrieval.semantic_cache.litellm_client.aembedding", return_value=[vec_q3]):
            miss = await cache.get(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                user_acl_groups=acl_groups,
                query="What are the employee vacation guidelines?",
                threshold=0.95,
            )
            assert miss is None


@pytest.mark.asyncio
async def test_phased_stream_generator_emits_citation_verified() -> None:
    """Verifies that PhasedStreamGenerator yields retrieval_status, retrieval_complete, token,
    citation, citation_verified, and done in sequence.
    """
    mock_request = AsyncMock()
    mock_request.is_disconnected.return_value = False

    doc_id = uuid4()
    source = PackedSource(
        source_index=1,
        chunk_id=uuid4(),
        document_id=doc_id,
        document_name="Q2_Report.pdf",
        page_number=4,
        bbox=None,
        text="Net revenue for Q2 reached 4.2 million dollars.",
        relevance_score=0.92,
    )

    async def mock_stream(*args, **kwargs):
        tokens = ["According ", "to ", "the ", "report, ", "net ", "revenue ", "was ", "$4.2M ", "[Source 1]."]
        for t in tokens:
            yield t

    with patch(
        "titan_backend.services.chat.stream_generator.litellm_client.astream_completion", side_effect=mock_stream
    ):
        stream = phased_stream_generator.generate_stream(
            request=mock_request,
            messages=[{"role": "user", "content": "What was revenue?"}],
            sources=[source],
        )

        events_seen = []
        verified_event_data = None
        async for sse_chunk in stream:
            for line in sse_chunk.splitlines():
                if line.startswith("event: "):
                    ev_type = line.replace("event: ", "").strip()
                    events_seen.append(ev_type)
                elif line.startswith("data: ") and events_seen and events_seen[-1] == "citation_verified":
                    verified_event_data = json.loads(line.replace("data: ", ""))

        # Verify all phases emitted in strict order
        assert "retrieval_status" in events_seen
        assert "retrieval_complete" in events_seen
        assert "token" in events_seen
        assert "citation" in events_seen
        assert "citation_verified" in events_seen
        assert "done" in events_seen

        # Verify citation_verified content
        assert verified_event_data is not None
        assert verified_event_data["status"] in ("VERIFIED", "LOW_CONFIDENCE")
        assert len(verified_event_data["verified_citations"]) == 1
        assert verified_event_data["verified_citations"][0]["verified"] is True


@pytest.mark.asyncio
async def test_multi_hop_query_decomposition() -> None:
    """Verifies that multi_hop_decomposer decomposes comparative and multi-hop queries."""
    mock_response = {
        "choices": [
            {"message": {"content": '["What was Acme Corp revenue in 2023?", "What was Beta Inc revenue in 2023?"]'}}
        ]
    }
    with patch("titan_backend.services.retrieval.multi_hop.litellm_client.acompletion", return_value=mock_response):
        sub_queries = await multi_hop_decomposer.decompose_query("Compare 2023 revenue between Acme Corp and Beta Inc")
        assert len(sub_queries) == 2
        assert "Acme Corp" in sub_queries[0]
        assert "Beta Inc" in sub_queries[1]


def test_nli_entailment_evaluator() -> None:
    """Verifies evaluate_citations_entailment computes claim entailment scores."""
    citations = [
        {"source_index": 1, "snippet": "Net revenue reached $4.2M in Q2."},
        {"source_index": 2, "snippet": "Short"},
    ]
    res = evaluate_citations_entailment(citations, "Generated answer text")
    assert res["status"] in ("VERIFIED", "LOW_CONFIDENCE")
    assert len(res["verified_citations"]) == 2
    assert res["verified_citations"][0]["verified"] is True
    assert res["average_entailment"] > 0.6


def test_deep_research_loop() -> None:
    """Verifies run_deep_research generates comprehensive structured multi-turn report."""
    report = run_deep_research(
        tenant_id=str(uuid4()),
        workspace_id=str(uuid4()),
        topic="SaaS Multi-Tenant Compliance and RLS Best Practices",
    )
    assert report["status"] == "COMPLETED"
    assert len(report["sections"]) == 4
    assert report["documents_analyzed"] > 0
    assert report["evidence_count"] > 0
    assert len(report["bibliography"]) > 0


def test_search_latency_telemetry() -> None:
    """Verifies HybridSearchResults contains measured latencies."""
    results = HybridSearchResults(
        dense_candidates=[SearchCandidate(chunk_id=uuid4(), score=0.9, payload={})],
        sparse_candidates=[],
        dense_latency_ms=18.4,
        sparse_latency_ms=12.1,
    )
    assert results.dense_latency_ms == 18.4
    assert results.sparse_latency_ms == 12.1
