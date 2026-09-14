import uuid
from uuid import UUID

from titan_backend.api.v1.schemas.chat import GroundingMode, PipelineMode
from titan_backend.services.chat.citations import citation_extractor
from titan_backend.services.retrieval.candidate_validator import ValidatedCandidate
from titan_backend.services.retrieval.classifier import QueryIntent, classifier
from titan_backend.services.retrieval.context_packer import PackedSource, context_packer
from titan_backend.services.retrieval.crag import crag_gate
from titan_backend.services.retrieval.fusion import fusion_engine
from titan_backend.services.retrieval.prompts import prompt_engine
from titan_backend.services.retrieval.reranker import RerankedCandidate
from titan_backend.services.retrieval.search import SearchCandidate
from titan_backend.services.retrieval.token_budget import token_budget_manager


def test_classifier_fast_path_latency_and_routing() -> None:
    # Chit-chat
    res_chitchat = classifier.classify("Hello!")
    assert res_chitchat.intent == QueryIntent.CHITCHAT
    assert res_chitchat.classification_latency_ms < 25.0
    assert res_chitchat.chitchat_response is not None

    # Meta
    res_meta = classifier.classify("What can you do?")
    assert res_meta.intent == QueryIntent.META
    assert res_meta.classification_latency_ms < 25.0

    # RAG Query
    res_rag = classifier.classify("What are the payment terms in section 4?")
    assert res_rag.intent == QueryIntent.RAG_QUERY
    assert res_rag.recommended_mode == PipelineMode.FAST

    # Comparative complex query -> DEEP
    res_deep = classifier.classify("Compare the difference between contract A and contract B")
    assert res_deep.intent == QueryIntent.RAG_QUERY
    assert res_deep.recommended_mode == PipelineMode.DEEP


def test_fusion_engine_rrf_and_alpha_blending() -> None:
    c1 = UUID("11111111-1111-1111-1111-111111111111")
    c2 = UUID("22222222-2222-2222-2222-222222222222")
    c3 = UUID("33333333-3333-3333-3333-333333333333")

    dense_candidates = [
        SearchCandidate(chunk_id=c1, score=0.9, payload={"text": "chunk 1"}),
        SearchCandidate(chunk_id=c2, score=0.8, payload={"text": "chunk 2"}),
    ]
    sparse_candidates = [
        SearchCandidate(chunk_id=c2, score=5.4, payload={"text": "chunk 2"}),
        SearchCandidate(chunk_id=c3, score=4.1, payload={"text": "chunk 3"}),
    ]

    fused = fusion_engine.fuse(dense_candidates, sparse_candidates, alpha=0.7, top_k=5)
    assert len(fused) == 3
    # c2 appeared in both dense (rank 2) and sparse (rank 1), so it gets high combined score
    fused_ids = [f.chunk_id for f in fused]
    assert c1 in fused_ids
    assert c2 in fused_ids
    assert c3 in fused_ids


def test_crag_gate_rejects_low_confidence() -> None:
    c_dummy = ValidatedCandidate(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_name="Doc.pdf",
        parent_chunk_id=None,
        section_heading=None,
        page_number=1,
        bbox=None,
        chunk_text="text",
    )

    # Low score candidate (< 0.40)
    low_candidates = [RerankedCandidate(chunk_id=c_dummy.chunk_id, relevance_score=0.25, candidate=c_dummy)]
    decision = crag_gate.evaluate(low_candidates, threshold=0.40)
    assert not decision.passed
    assert decision.reason == "INSUFFICIENT_CONTEXT"
    assert decision.refusal_message is not None

    # High score candidate (>= 0.40)
    high_candidates = [RerankedCandidate(chunk_id=c_dummy.chunk_id, relevance_score=0.85, candidate=c_dummy)]
    decision_pass = crag_gate.evaluate(high_candidates, threshold=0.40)
    assert decision_pass.passed
    assert decision_pass.reason == "CONFIDENT"


def test_context_packer_lost_in_the_middle_ordering() -> None:
    c_objs = [
        ValidatedCandidate(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            document_name=f"Doc_{i}.pdf",
            parent_chunk_id=None,
            section_heading=None,
            page_number=i,
            bbox=None,
            chunk_text=f"Text {i}",
        )
        for i in range(5)
    ]
    reranked_list = [
        RerankedCandidate(chunk_id=c_objs[i].chunk_id, relevance_score=0.9 - (i * 0.1), candidate=c_objs[i])
        for i in range(5)
    ]

    reordered = context_packer.reorder_lost_in_the_middle(reranked_list)
    assert len(reordered) == 5
    # High relevance placed at edges: position 0 has highest, last position has 2nd highest
    assert reordered[0].relevance_score == reranked_list[0].relevance_score
    assert reordered[-1].relevance_score == reranked_list[1].relevance_score


def test_prompt_engine_renders_grounding_templates() -> None:
    source = PackedSource(
        source_index=1,
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_name="Agreement.pdf",
        page_number=3,
        bbox=None,
        text="All notices shall be provided in writing within 30 days.",
        relevance_score=0.88,
    )
    prompt = prompt_engine.render_system_prompt([source], grounding_mode=GroundingMode.STRICT)
    assert "STRICT grounding constraints" in prompt
    assert "[Source 1]" in prompt
    assert "Agreement.pdf" in prompt
    assert "All notices shall be provided in writing within 30 days." in prompt


def test_citation_extractor_links_sources() -> None:
    doc_id = uuid.uuid4()
    source1 = PackedSource(
        source_index=1,
        chunk_id=uuid.uuid4(),
        document_id=doc_id,
        document_name="Policy.pdf",
        page_number=2,
        bbox={"x": 10, "y": 20},
        text="Employees receive 20 days of paid annual leave.",
        relevance_score=0.91,
    )

    answer_text = "According to company policy, employees receive 20 days of paid annual leave [Source 1]."
    citations = citation_extractor.extract_citations(answer_text, [source1])
    assert len(citations) == 1
    assert citations[0].source_index == 1
    assert citations[0].document_name == "Policy.pdf"
    assert citations[0].page_number == 2
    assert "20 days of paid annual leave" in citations[0].snippet


def test_token_budget_manager_truncation() -> None:
    messages = [
        {"role": "user", "content": "Query 1: " + "a" * 500},
        {"role": "assistant", "content": "Answer 1: " + "b" * 500},
        {"role": "user", "content": "Query 2: " + "c" * 200},
    ]
    truncated = token_budget_manager.truncate_chat_history(messages, max_history_tokens=100)
    # The newest message should be preserved
    assert len(truncated) >= 1
    assert truncated[-1]["content"].startswith("Query 2:")
