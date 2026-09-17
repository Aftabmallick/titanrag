import asyncio
import json
import time
from collections.abc import AsyncGenerator
from typing import Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from titan_workers.tasks.deep_research import execute_deep_research

from titan_backend.api.v1.acl_groups import resolve_user_acl_groups
from titan_backend.api.v1.events import broadcast_event
from titan_backend.api.v1.schemas.chat import (
    ChatMessageResponse,
    ChatQueryRequest,
    ChatSessionCreate,
    ChatSessionResponse,
    ChatSessionUpdate,
    CompareDocumentsRequest,
    DeepResearchRequest,
    PipelineMode,
    RegenerateRequest,
    SharedSessionDetailResponse,
    ShareSessionResponse,
)
from titan_backend.core.audit import record_audit_event
from titan_backend.core.dependencies import CurrentUser, get_current_user, require_permission
from titan_backend.core.errors import AppException
from titan_backend.core.guardrails.injection import sanitize_and_isolate_query
from titan_backend.core.logging import logger
from titan_backend.core.quotas import preflight_chat_quota, record_chat_token_usage
from titan_backend.core.rbac import Permission
from titan_backend.db.models.chat import MessageRole
from titan_backend.db.models.finops import FinOpsOperation
from titan_backend.db.models.promptops import PromptEnvironment
from titan_backend.db.models.settings import RAGSettings
from titan_backend.db.models.workspaces import Workspace
from titan_backend.db.session import get_db
from titan_backend.services.ab_testing.router import ABExperimentRouter
from titan_backend.services.chat.session_service import session_service
from titan_backend.services.chat.stream_generator import format_sse, phased_stream_generator
from titan_backend.services.chat.suggestions import suggestions_generator
from titan_backend.services.finops.gatekeeper import FinOpsGatekeeper
from titan_backend.services.finops.ledger import FinOpsLedgerService
from titan_backend.services.promptops.engine import PromptOpsEngine
from titan_backend.services.retrieval.candidate_validator import candidate_validator
from titan_backend.services.retrieval.classifier import QueryIntent, classifier
from titan_backend.services.retrieval.context_packer import context_packer
from titan_backend.services.retrieval.crag import crag_gate
from titan_backend.services.retrieval.fusion import fusion_engine
from titan_backend.services.retrieval.hyde import hyde_generator
from titan_backend.services.retrieval.multi_hop import multi_hop_decomposer
from titan_backend.services.retrieval.prompts import prompt_engine
from titan_backend.services.retrieval.reranker import RerankedCandidate, reranker
from titan_backend.services.retrieval.rewriter import query_rewriter
from titan_backend.services.retrieval.search import (
    HybridSearchResults,
    SearchCandidate,
    hybrid_search_engine,
)
from titan_backend.services.retrieval.self_query import self_query_engine
from titan_backend.services.retrieval.semantic_cache import semantic_cache
from titan_backend.services.retrieval.source_comparator import source_comparator
from titan_backend.services.observability.langfuse_client import LLMOpsSpan, LLMOpsTrace, llmops_tracer

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["Chat & Retrieval"])


async def get_or_create_workspace_settings(db: AsyncSession, tenant_id: UUID, workspace_id: UUID) -> RAGSettings:
    stmt = select(RAGSettings).where(
        RAGSettings.workspace_id == workspace_id,
        RAGSettings.tenant_id == tenant_id,
    )
    res = await db.execute(stmt)
    settings_obj = res.scalar_one_or_none()
    if not settings_obj:
        settings_obj = RAGSettings(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            retrieval_mode="HYBRID",
            dense_weight=0.7,
            sparse_weight=0.3,
            top_k=20,
            rerank_top_k=5,
            score_threshold=0.40,
            context_window_strategy="HIERARCHICAL",
        )
        db.add(settings_obj)
        await db.commit()
        await db.refresh(settings_obj)
    return settings_obj


@router.post("/chat", response_class=StreamingResponse)
async def chat_endpoint(
    workspace_id: UUID,
    payload: ChatQueryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission(Permission.SEARCH)),
) -> StreamingResponse:
    """Primary chat endpoint executing multi-stage hybrid search, reranking, and grounded streaming

    generation.
    """
    # 1. FinOps pre-flight check & atomic Compute Unit quota verification
    workspace_obj = await db.get(Workspace, workspace_id)
    ws_meta = getattr(workspace_obj, "settings", {}) or {}
    quota_cfg = ws_meta.get("quota_limits", {}) if isinstance(ws_meta, dict) else {}
    max_cu_cap = float(quota_cfg.get("max_compute_units", 0.0))
    await FinOpsGatekeeper.check_and_reserve_quota(
        tenant_id=current_user.tenant_id,
        estimated_cu=1.0,
        max_monthly_cu=max_cu_cap if max_cu_cap > 0 else None,
    )
    await preflight_chat_quota(current_user.tenant_id)

    # 2. Prompt injection sanitization & canary injection
    sanitized = sanitize_and_isolate_query(payload.query)

    # 3. Fast-Path In-Process Intent Classifier (<15ms)
    classification = classifier.classify(sanitized.clean_text, payload.pipeline_mode)

    # Handle Chit-chat
    if classification.intent == QueryIntent.CHITCHAT:

        async def chitchat_stream() -> AsyncGenerator[str, None]:
            yield format_sse("token", {"token": classification.chitchat_response or "Hello!"})
            yield format_sse("done", {"tokens_generated": 15, "intent": "CHITCHAT"})

        return StreamingResponse(chitchat_stream(), media_type="text/event-stream")

    # Handle Meta inquiries
    if classification.intent == QueryIntent.META:

        async def meta_stream() -> AsyncGenerator[str, None]:
            yield format_sse("token", {"token": classification.meta_response or "TitanRAG Knowledge Engine."})
            yield format_sse("done", {"tokens_generated": 25, "intent": "META"})

        return StreamingResponse(meta_stream(), media_type="text/event-stream")

    # 4. Resolve RAG Settings for Workspace & Dynamic A/B Experiment Overrides
    rag_settings = await get_or_create_workspace_settings(db, current_user.tenant_id, workspace_id)
    exp_override, experiment_id, exp_variant = await ABExperimentRouter.get_active_experiment_override(
        session=db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    if exp_override:
        if "alpha" in exp_override:
            rag_settings.dense_weight = float(exp_override["alpha"])
            rag_settings.sparse_weight = round(1.0 - float(exp_override["alpha"]), 2)
        if "top_k" in exp_override:
            rag_settings.top_k = int(exp_override["top_k"])
        if "top_n" in exp_override or "rerank_top_k" in exp_override:
            rag_settings.rerank_top_k = int(
                exp_override.get("rerank_top_k", exp_override.get("top_n", rag_settings.rerank_top_k))
            )
        if "confidence_threshold" in exp_override or "score_threshold" in exp_override:
            rag_settings.score_threshold = float(
                exp_override.get(
                    "score_threshold", exp_override.get("confidence_threshold", rag_settings.score_threshold)
                )
            )
        if "model" in exp_override and not payload.model_override:
            payload.model_override = str(exp_override["model"])

    # 5. Resolve user effective ACL groups with Redis cache & compaction
    user_groups = await resolve_user_acl_groups(
        user_id=current_user.id,
        workspace_id=workspace_id,
        db=db,
    )
    if rag_settings.semantic_cache_enabled:
        cached = await semantic_cache.get(
            tenant_id=current_user.tenant_id,
            workspace_id=workspace_id,
            user_acl_groups=user_groups,
            query=sanitized.clean_text,
        )
        if cached:

            async def cache_stream() -> AsyncGenerator[str, None]:
                yield format_sse("retrieval_complete", {"sources": cached.sources, "cached": True})
                yield format_sse("token", {"token": cached.content})
                yield format_sse("citation", {"citations": cached.citations})
                yield format_sse(
                    "done",
                    {
                        "cached": True,
                        "tokens_generated": cached.tokens_used,
                        "full_text": cached.content,
                        "citations": cached.citations,
                    },
                )

            return StreamingResponse(cache_stream(), media_type="text/event-stream")

    # 6. Resolve Session and Chat History
    chat_history: list[dict[str, str]] = []
    session = None
    if payload.session_id:
        session = await session_service.get_session(db, payload.session_id, current_user.tenant_id, workspace_id)
        past_msgs = await session_service.get_messages(db, session.id, limit=6)
        chat_history = [{"role": m.role.lower(), "content": m.content} for m in past_msgs]

    # 7. Deep-Path Query Reformulation (if history exists)
    search_query = sanitized.clean_text
    if chat_history and classification.recommended_mode == PipelineMode.DEEP:
        search_query = await query_rewriter.rewrite_query(search_query, chat_history)

    # 8. Self-Querying Metadata Extraction (Deep-Path)
    folder_filter = payload.folder
    doc_type_filter = None
    tags_filter = payload.tags
    if classification.recommended_mode == PipelineMode.DEEP:
        extracted_filters = await self_query_engine.extract_filters(search_query)
        search_query = extracted_filters.cleaned_query
        if extracted_filters.folder and not folder_filter:
            folder_filter = extracted_filters.folder
        if extracted_filters.doc_type:
            doc_type_filter = extracted_filters.doc_type

    # 9. HyDE (Hypothetical Document Embeddings) if enabled
    dense_query_text = search_query
    if rag_settings.hyde_enabled:
        dense_query_text = await hyde_generator.generate_hypothetical_document(search_query)

    # 10. Multi-Stage Hybrid Search (Parallel Dense + BM25 with Multi-Hop support)
    # LLMOps Trace Registration
    trace = LLMOpsTrace(
        workspace_id=workspace_id,
        user_id=current_user.id,
        query=sanitized.clean_text,
        session_id=session.id if session else None,
        tags=[f"mode:{classification.recommended_mode.value}"],
    )
    llmops_tracer.provider.create_trace(trace)

    sub_queries = [dense_query_text]
    if classification.recommended_mode == PipelineMode.DEEP:
        decomposed = await multi_hop_decomposer.decompose_query(search_query)
        if len(decomposed) > 1:
            sub_queries = decomposed

    all_dense_candidates: list[SearchCandidate] = []
    all_sparse_candidates: list[SearchCandidate] = []

    if len(sub_queries) > 1:
        search_tasks = [
            hybrid_search_engine.search(
                query=sq,
                tenant_id=current_user.tenant_id,
                workspace_id=workspace_id,
                user_acl_groups=user_groups,
                top_k=max(10, rag_settings.top_k // len(sub_queries)),
                document_ids=payload.document_ids,
                folder=folder_filter,
                tags=tags_filter,
                doc_type=doc_type_filter,
            )
            for sq in sub_queries
        ]
        multi_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        for res in multi_results:
            if isinstance(res, HybridSearchResults):
                all_dense_candidates.extend(res.dense_candidates)
                all_sparse_candidates.extend(res.sparse_candidates)
    else:
        search_results = await hybrid_search_engine.search(
            query=sub_queries[0],
            tenant_id=current_user.tenant_id,
            workspace_id=workspace_id,
            user_acl_groups=user_groups,
            top_k=rag_settings.top_k,
            document_ids=payload.document_ids,
            folder=folder_filter,
            tags=tags_filter,
            doc_type=doc_type_filter,
        )
        all_dense_candidates = search_results.dense_candidates
        all_sparse_candidates = search_results.sparse_candidates

    # Deduplicate candidates across sub-queries preserving highest individual scores
    unique_dense: dict[UUID, SearchCandidate] = {}
    for c in all_dense_candidates:
        if c.chunk_id not in unique_dense or c.score > unique_dense[c.chunk_id].score:
            unique_dense[c.chunk_id] = c
    unique_sparse: dict[UUID, SearchCandidate] = {}
    for c in all_sparse_candidates:
        if c.chunk_id not in unique_sparse or c.score > unique_sparse[c.chunk_id].score:
            unique_sparse[c.chunk_id] = c

    dense_candidates_list = list(unique_dense.values())
    sparse_candidates_list = list(unique_sparse.values())

    # 11. Zero-Trust PostgreSQL Candidate Barrier
    all_candidate_ids = [c.chunk_id for c in dense_candidates_list] + [c.chunk_id for c in sparse_candidates_list]
    validated_candidates_map = await candidate_validator.validate_candidates(
        db=db,
        candidate_ids=all_candidate_ids,
        tenant_id=current_user.tenant_id,
        workspace_id=workspace_id,
    )

    # Filter candidates to only validated chunks
    dense_validated = [c for c in dense_candidates_list if c.chunk_id in validated_candidates_map]
    sparse_validated = [c for c in sparse_candidates_list if c.chunk_id in validated_candidates_map]

    # 12. Tiered Fusion (RRF + Alpha Blending)
    fused_candidates = fusion_engine.fuse(
        dense_candidates=dense_validated,
        sparse_candidates=sparse_validated,
        alpha=rag_settings.dense_weight,
        top_k=25,
    )

    fused_validated_objects = [
        validated_candidates_map[fc.chunk_id] for fc in fused_candidates if fc.chunk_id in validated_candidates_map
    ]

    # 13. Cross-Encoder Reranking with 400ms Circuit Breaker
    reranked = await reranker.rerank(
        query=search_query,
        candidates=fused_validated_objects,
        top_n=rag_settings.rerank_top_k,
    )

    # 14. CRAG Confidence Gate
    crag_decision = crag_gate.evaluate(reranked, threshold=rag_settings.score_threshold)
    if not crag_decision.passed:
        crag_span = LLMOpsSpan(
            name="crag_confidence_gate",
            parent_trace_id=trace.trace_id,
            metadata={"crag_passed": False, "score_threshold": rag_settings.score_threshold},
        )
        crag_span.set_output(crag_decision.refusal_message)
        trace.spans.append(crag_span)
        llmops_tracer.provider.record_span(trace, crag_span)
        trace.end_time = time.time()
        llmops_tracer.provider.finalize_trace(trace)

        async def refusal_stream() -> AsyncGenerator[str, None]:
            refusal = crag_decision.refusal_message or "Insufficient context."
            yield format_sse("token", {"token": refusal})
            yield format_sse("done", {"tokens_generated": 20, "crag_passed": False, "full_text": refusal})

        return StreamingResponse(refusal_stream(), media_type="text/event-stream")

    # 15. Context Packing & Parent Context Injection
    packed_sources = await context_packer.pack_context(
        candidates=reranked,
        db=db,
        parent_context_enabled=rag_settings.parent_context_enabled,
    )

    # Record retrieval span
    retrieval_span = LLMOpsSpan(
        name="hybrid_retrieval",
        parent_trace_id=trace.trace_id,
        metadata={
            "dense_weight": rag_settings.dense_weight,
            "sparse_weight": rag_settings.sparse_weight,
            "top_k": rag_settings.top_k,
            "rerank_top_k": rag_settings.rerank_top_k,
            "sources_count": len(packed_sources),
            "reranked_top_score": float(reranked[0].rerank_score) if reranked else 0.0,
        },
    )
    trace.spans.append(retrieval_span)
    llmops_tracer.provider.record_span(trace, retrieval_span)

    # 16. System Prompt Assembly (PromptOps registry integration)
    active_prod_prompt = await PromptOpsEngine.get_active_prompt(
        session=db,
        workspace_id=workspace_id,
        slug="system_chat",
        environment=PromptEnvironment.PROD,
    )
    system_prompt = prompt_engine.render_system_prompt(
        sources=packed_sources,
        grounding_mode=payload.grounding_mode,
        custom_override=active_prod_prompt or rag_settings.system_prompt_override,
    )

    llm_messages = [{"role": "system", "content": system_prompt}]
    llm_messages.extend(chat_history)
    llm_messages.append({"role": "user", "content": sanitized.clean_text})

    # Record User Message
    if session:
        await session_service.add_message(
            db=db,
            session_id=session.id,
            role=MessageRole.USER,
            content=sanitized.clean_text,
        )

    # 17. Return Phased Streaming Generator
    async def wrapped_stream() -> AsyncGenerator[str, None]:
        full_text = ""
        citations_list = []
        tokens_count = 0

        async for chunk in phased_stream_generator.generate_stream(
            request=request,
            messages=llm_messages,
            sources=packed_sources,
            model=payload.model_override,
            temperature=payload.temperature or 0.2,
            session_id=session.id if session else None,
            canary_token=sanitized.canary_token,
        ):
            if chunk.startswith("event: token"):
                try:
                    data = json.loads(chunk.split("data: ")[1])
                    full_text += data.get("token", "")
                    tokens_count += 1
                except Exception:
                    pass
            elif chunk.startswith("event: citation\n"):
                try:
                    data = json.loads(chunk.split("data: ")[1])
                    citations_list = data.get("citations", [])
                except Exception:
                    pass

            yield chunk

        # Post-stream persistence and FinOps accounting
        try:
            if session:
                await session_service.add_message(
                    db=db,
                    session_id=session.id,
                    role=MessageRole.ASSISTANT,
                    content=full_text,
                    citations=citations_list,
                    tokens_used=tokens_count,
                )
                await session_service.maybe_auto_title(db, session, sanitized.clean_text)

            # Record CU tokens in Redis/FinOps
            await record_chat_token_usage(current_user.tenant_id, tokens_count)

            # Phase 6: FinOps atomic quota update and persistent audit ledger
            cu_consumed = max(0.01, round(tokens_count / 1000.0 * 2.0, 4))
            await FinOpsGatekeeper.record_usage(
                tenant_id=current_user.tenant_id,
                cu_consumed=cu_consumed,
                max_monthly_cu=max_cu_cap if max_cu_cap > 0 else None,
            )
            finops_op = (
                FinOpsOperation.CHAT_DEEP
                if classification.recommended_mode == PipelineMode.DEEP
                else FinOpsOperation.CHAT_FAST
            )
            await FinOpsLedgerService.record_transaction(
                session=db,
                tenant_id=current_user.tenant_id,
                workspace_id=workspace_id,
                operation_type=finops_op,
                prompt_tokens=max(1, len(sanitized.clean_text.split()) * 2),
                completion_tokens=tokens_count,
                user_id=current_user.id,
                model_name=payload.model_override or "gpt-4o",
                provider="litellm",
                details={
                    "experiment_id": str(experiment_id) if experiment_id else None,
                    "experiment_variant": exp_variant,
                    "pipeline_mode": classification.recommended_mode.value,
                },
            )

            # Record LLMOps generation span and finalize external trace (Phoenix / Langfuse)
            try:
                gen_span = LLMOpsSpan(
                    name="generation",
                    parent_trace_id=trace.trace_id,
                    metadata={
                        "model": payload.model_override or "gpt-4o",
                        "usage": {
                            "prompt_tokens": max(1, len(sanitized.clean_text.split()) * 2),
                            "completion_tokens": tokens_count,
                            "total_tokens": max(1, len(sanitized.clean_text.split()) * 2) + tokens_count,
                        },
                        "output": full_text[:1000],
                    },
                )
                trace.spans.append(gen_span)
                llmops_tracer.provider.record_span(trace, gen_span)
                trace.total_tokens = tokens_count
                trace.end_time = time.time()
                llmops_tracer.provider.finalize_trace(trace)
            except Exception as trace_err:
                logger.warning("llmops_trace_record_failed", error=str(trace_err))

            # Store in semantic cache
            if rag_settings.semantic_cache_enabled and full_text:
                serialized_sources = [
                    {
                        "source_index": s.source_index,
                        "document_name": s.document_name,
                        "document_id": str(s.document_id),
                        "page_number": s.page_number,
                        "relevance_score": s.relevance_score,
                    }
                    for s in packed_sources
                ]
                await semantic_cache.set(
                    tenant_id=current_user.tenant_id,
                    workspace_id=workspace_id,
                    user_acl_groups=user_groups,
                    query=sanitized.clean_text,
                    content=full_text,
                    citations=citations_list,
                    sources=serialized_sources,
                    tokens_used=tokens_count,
                    ttl_seconds=rag_settings.cache_ttl_seconds,
                )

            # Audit log document search and cited sources
            await record_audit_event(
                session=db,
                tenant_id=current_user.tenant_id,
                user_id=current_user.id,
                action="DOCUMENT_SEARCH",
                resource_type="workspace",
                resource_id=str(workspace_id),
                details={
                    "query": sanitized.clean_text,
                    "matched_chunks": [str(s.chunk_id) for s in packed_sources],
                    "matched_count": len(packed_sources),
                },
                ip_address=request.client.host if request.client else None,
            )
            if citations_list:
                await record_audit_event(
                    session=db,
                    tenant_id=current_user.tenant_id,
                    user_id=current_user.id,
                    action="DOCUMENT_CITED",
                    resource_type="chat_session",
                    resource_id=str(session.id) if session else None,
                    details={
                        "citations": citations_list,
                        "citation_count": len(citations_list),
                    },
                    ip_address=request.client.host if request.client else None,
                )

            # Broadcast system event
            await broadcast_event(
                "query.completed",
                {
                    "workspace_id": str(workspace_id),
                    "tokens": tokens_count,
                    "citations_count": len(citations_list),
                },
                tenant_id=str(current_user.tenant_id),
            )

        except Exception as e:
            logger.error("post_stream_persistence_error", error=str(e))

    return StreamingResponse(
        wrapped_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------- Chat Sessions Endpoints ---------------- #


@router.post("/chat-sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    workspace_id: UUID,
    payload: ChatSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission(Permission.SEARCH)),
) -> ChatSessionResponse:
    """Create a new chat conversation session."""
    return await session_service.create_session(
        db=db,
        tenant_id=current_user.tenant_id,
        workspace_id=workspace_id,
        user_id=current_user.user_id,
        title=payload.title or "New Chat",
        meta=payload.meta,
    )


@router.get("/chat-sessions", response_model=list[ChatSessionResponse])
async def list_chat_sessions(
    workspace_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission(Permission.SEARCH)),
) -> list[ChatSessionResponse]:
    """List chat sessions for the current user in this workspace."""
    return await session_service.list_sessions(
        db=db,
        tenant_id=current_user.tenant_id,
        workspace_id=workspace_id,
        user_id=current_user.user_id,
        limit=limit,
        offset=offset,
    )


@router.get("/chat-sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
async def get_session_messages(
    workspace_id: UUID,
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission(Permission.SEARCH)),
) -> list[ChatMessageResponse]:
    """Retrieve message history for a specific chat session."""
    await session_service.get_session(db, session_id, current_user.tenant_id, workspace_id)
    return await session_service.get_messages(db, session_id)


@router.patch("/chat-sessions/{session_id}", response_model=ChatSessionResponse)
async def rename_chat_session(
    workspace_id: UUID,
    session_id: UUID,
    payload: ChatSessionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission(Permission.SEARCH)),
) -> ChatSessionResponse:
    """Rename chat session."""
    if not payload.title:
        session = await session_service.get_session(db, session_id, current_user.tenant_id, workspace_id)
        return ChatSessionResponse(
            id=session.id,
            tenant_id=session.tenant_id,
            workspace_id=session.workspace_id,
            user_id=session.user_id,
            title=session.title,
            created_at=session.created_at.isoformat(),
            updated_at=session.updated_at.isoformat(),
            meta=session.meta,
        )
    return await session_service.update_title(
        db=db,
        session_id=session_id,
        tenant_id=current_user.tenant_id,
        workspace_id=workspace_id,
        new_title=payload.title,
    )


@router.delete("/chat-sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    workspace_id: UUID,
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission(Permission.SEARCH)),
) -> Response:
    """Delete a chat session and all its messages."""
    await session_service.delete_session(db, session_id, current_user.tenant_id, workspace_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/chat-sessions/{session_id}/export")
async def export_chat_session(
    workspace_id: UUID,
    session_id: UUID,
    format: str = Query("markdown", pattern="^(markdown|json)$"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission(Permission.SEARCH)),
) -> Response:
    """Export conversation session as formatted Markdown or structured JSON."""
    session = await session_service.get_session(db, session_id, current_user.tenant_id, workspace_id)
    if format == "json":
        messages = await session_service.get_messages(db, session.id)
        export_data = {
            "session_id": str(session.id),
            "title": session.title,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
            "messages": [m.model_dump() for m in messages],
        }
        return Response(
            content=json.dumps(export_data, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="chat_{session.title[:30]}.json"'},
        )

    md_content = await session_service.export_markdown(db, session)
    return Response(
        content=md_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="chat_{session.title[:30]}.md"'},
    )


@router.post("/chat-sessions/{session_id}/share", response_model=ShareSessionResponse)
async def share_chat_session(
    workspace_id: UUID,
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission(Permission.SEARCH)),
) -> ShareSessionResponse:
    """Generate a shareable read-only link token for a chat session."""
    session = await session_service.get_session(db, session_id, current_user.tenant_id, workspace_id)
    token = await session_service.create_share_link(session.id)
    return ShareSessionResponse(
        session_id=session.id,
        share_token=token,
        share_url=f"/shared/chat/{token}",
    )


@router.get("/chat-sessions/shared/{share_token}", response_model=SharedSessionDetailResponse)
async def get_shared_chat_session(
    workspace_id: UUID,
    share_token: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission(Permission.SEARCH)),
) -> SharedSessionDetailResponse:
    """Retrieve a shared chat session and its message history using a share token."""
    session_id = await session_service.get_shared_session_id(share_token)
    if not session_id:
        raise AppException(
            message="Shared chat link is invalid or has expired",
            status_code=404,
            error_code="SHARE_LINK_NOT_FOUND",
        )
    session = await session_service.get_session(db, session_id, current_user.tenant_id, workspace_id)
    messages = await session_service.get_messages(db, session.id)
    return SharedSessionDetailResponse(
        session=ChatSessionResponse.model_validate(session),
        messages=messages,
    )


@router.get("/chat-sessions/{session_id}/suggestions", response_model=list[str])
async def get_follow_up_suggestions(
    workspace_id: UUID,
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission(Permission.SEARCH)),
) -> list[str]:
    """Generate 2-3 follow-up question suggestions based on the last response in the session."""
    messages = await session_service.get_messages(db, session_id, limit=2)
    if not messages:
        return []
    last_assistant_msg = next((m for m in reversed(messages) if m.role == "ASSISTANT"), None)
    last_user_msg = next((m for m in reversed(messages) if m.role == "USER"), None)
    if not last_assistant_msg or not last_user_msg:
        return []
    return await suggestions_generator.generate_suggestions(last_user_msg.content, last_assistant_msg.content)


@router.post("/chat-sessions/{session_id}/regenerate", response_class=StreamingResponse)
async def regenerate_answer(
    workspace_id: UUID,
    session_id: UUID,
    payload: RegenerateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission(Permission.SEARCH)),
) -> StreamingResponse:
    """Regenerates the assistant's last response, either with fresh search or reusing context."""
    messages = await session_service.get_messages(db, session_id, limit=4)
    last_user_msg = next((m for m in reversed(messages) if m.role == "USER"), None)
    if not last_user_msg:
        raise AppException("No user query found to regenerate.", status_code=400, error_code="NO_QUERY_FOUND")

    # Delegate to primary chat execution with the last user query
    chat_req = ChatQueryRequest(
        query=last_user_msg.content,
        session_id=session_id,
        stream=True,
    )
    return await chat_endpoint(
        workspace_id=workspace_id,
        payload=chat_req,
        request=request,
        db=db,
        current_user=current_user,
        _=None,
    )


@router.post("/compare", response_class=StreamingResponse)
async def compare_documents(
    workspace_id: UUID,
    payload: CompareDocumentsRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission(Permission.SEARCH)),
) -> StreamingResponse:
    """Compares two documents on a specific topic with side-by-side citations."""
    user_groups = await resolve_user_acl_groups(
        user_id=current_user.id,
        workspace_id=workspace_id,
        db=db,
    )

    # Retrieve from Doc A
    res_a = await hybrid_search_engine.search(
        query=payload.topic,
        tenant_id=current_user.tenant_id,
        workspace_id=workspace_id,
        user_acl_groups=user_groups,
        document_ids=[payload.document_a_id],
        top_k=10,
    )
    # Retrieve from Doc B
    res_b = await hybrid_search_engine.search(
        query=payload.topic,
        tenant_id=current_user.tenant_id,
        workspace_id=workspace_id,
        user_acl_groups=user_groups,
        document_ids=[payload.document_b_id],
        top_k=10,
    )

    # Calibrated fusion across dense + sparse candidates per document
    fused_a = fusion_engine.fuse(res_a.dense_candidates, res_a.sparse_candidates, alpha=0.7, top_k=10)
    fused_b = fusion_engine.fuse(res_b.dense_candidates, res_b.sparse_candidates, alpha=0.7, top_k=10)

    all_ids = [c.chunk_id for c in fused_a + fused_b]
    validated = await candidate_validator.validate_candidates(db, all_ids, current_user.tenant_id, workspace_id)

    cands_a = [validated[c.chunk_id] for c in fused_a if c.chunk_id in validated]
    cands_b = [validated[c.chunk_id] for c in fused_b if c.chunk_id in validated]

    packed_a = await context_packer.pack_context(
        [RerankedCandidate(chunk_id=c.chunk_id, relevance_score=0.85, candidate=c) for c in cands_a[:5]],
        db=db,
    )
    packed_b = await context_packer.pack_context(
        [RerankedCandidate(chunk_id=c.chunk_id, relevance_score=0.85, candidate=c) for c in cands_b[:5]],
        db=db,
    )

    comparison_prompt = source_comparator.format_comparison_prompt(packed_a, packed_b, payload.topic)
    llm_msgs = [{"role": "user", "content": comparison_prompt}]

    return StreamingResponse(
        phased_stream_generator.generate_stream(
            request=request,
            messages=llm_msgs,
            sources=packed_a + packed_b,
        ),
        media_type="text/event-stream",
    )


@router.post("/deep-research", status_code=status.HTTP_202_ACCEPTED)
async def dispatch_deep_research(
    workspace_id: UUID,
    payload: DeepResearchRequest,
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission(Permission.SEARCH)),
) -> dict[str, Any]:
    """Dispatches an asynchronous deep research background task across 50+ documents."""
    task = execute_deep_research.delay(
        tenant_id=str(current_user.tenant_id),
        workspace_id=str(workspace_id),
        topic=payload.topic,
        session_id=str(payload.session_id) if payload.session_id else None,
    )
    return {
        "task_id": task.id,
        "status": "DISPATCHED",
        "topic": payload.topic,
        "message": "Deep research background task started.",
    }


@router.get("/deep-research/{task_id}")
async def get_deep_research_status(
    workspace_id: UUID,
    task_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission(Permission.SEARCH)),
) -> dict[str, Any]:
    """Poll status and retrieve results of an asynchronous deep research task."""
    from celery.result import AsyncResult
    from titan_workers.celery_app import celery_app

    from titan_backend.clients.redis_client import get_redis_client

    # 1. Check Redis cache first
    try:
        redis = await get_redis_client()
        cached = await redis.get(f"deep_research:{task_id}")
        if cached:
            return cast(dict[str, Any], json.loads(cached))
    except Exception:
        pass

    # 2. Inspect Celery AsyncResult
    result = AsyncResult(task_id, app=celery_app)
    if result.ready():
        if result.successful():
            report = result.result
            if isinstance(report, dict):
                try:
                    redis = await get_redis_client()
                    await redis.setex(f"deep_research:{task_id}", 7 * 86400, json.dumps(report))
                except Exception:
                    pass
                return report
            return {"status": "COMPLETED", "result": report}
        else:
            return {"status": "FAILED", "task_id": task_id, "error": str(result.result)}

    return {
        "status": "PROCESSING" if result.state == "PENDING" else result.state,
        "task_id": task_id,
        "message": "Deep research analysis in progress across workspace documentation.",
    }
