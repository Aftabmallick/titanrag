import asyncio
import json
import time
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID, uuid4

from fastapi import Request
from titan_backend.api.v1.schemas.chat import CitationPayload
from titan_backend.clients.litellm_client import litellm_client
from titan_backend.core.guardrails.egress_scanner import StreamingEgressScanner
from titan_backend.core.logging import logger
from titan_backend.services.chat.citations import citation_extractor
from titan_backend.services.retrieval.context_packer import PackedSource


def format_sse(event: str, data: dict[str, Any]) -> str:
    """Formats an SSE message."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class PhasedStreamGenerator:
    """Orchestrates phased SSE token generation with grounded sources, in-stream secret egress

    scanning, and socket disconnect cancellation.
    """

    def __init__(self) -> None:
        self.egress_scanner = StreamingEgressScanner(window_size=256)

    async def generate_stream(
        self,
        request: Request,
        messages: list[dict[str, str]],
        sources: list[PackedSource],
        model: str | None = None,
        temperature: float = 0.2,
        session_id: UUID | None = None,
        canary_token: str | None = None,
    ) -> AsyncGenerator[str, None]:
        start_time = time.perf_counter()
        full_content = ""
        tokens_count = 0

        # Phase 1: Emit retrieval status
        yield format_sse("retrieval_status", {
            "step": "retrieval_complete",
            "message": f"Retrieved and verified {len(sources)} candidate sources.",
        })

        # Phase 2: Emit source summary
        source_summaries = [
            {
                "source_index": s.source_index,
                "document_name": s.document_name,
                "document_id": str(s.document_id),
                "page_number": s.page_number,
                "relevance_score": s.relevance_score,
            }
            for s in sources
        ]
        yield format_sse("retrieval_complete", {"sources": source_summaries})

        # Phase 3: Token-by-token generation with disconnect monitoring & egress scanning
        try:
            stream_gen = litellm_client.astream_completion(
                messages=messages,
                model=model,
                temperature=temperature,
            )

            async for token in stream_gen:
                # Check client socket disconnect
                if await request.is_disconnected():
                    logger.info("client_socket_disconnected_aborting_stream", session_id=str(session_id))
                    return

                # Scan chunk for leaks
                scan_res = self.egress_scanner.scan_chunk(token)
                clean_token = scan_res.clean_chunk
                full_content += clean_token
                tokens_count += 1

                yield format_sse("token", {"token": clean_token})

            # Flush any remaining lookahead characters from egress scanner
            flushed_tail = self.egress_scanner.flush()
            if flushed_tail:
                full_content += flushed_tail
                tokens_count += 1
                yield format_sse("token", {"token": flushed_tail})

            # Check if canary token leaked
            if canary_token and canary_token in full_content:
                logger.error("canary_token_leaked_in_output", canary=canary_token)

            msg_id = str(uuid4())

            # Phase 4: Extract and emit citations
            citations: list[CitationPayload] = citation_extractor.extract_citations(full_content, sources)
            citations_data = [c.model_dump(mode="json") for c in citations]
            yield format_sse("citation", {"citations": citations_data})

            # Phase 4.5: Async NLI Claim Verification
            try:
                from titan_workers.tasks.nli_guardrail import evaluate_citations_entailment
                nli_result = evaluate_citations_entailment(
                    citations=citations_data,
                    generated_text=full_content,
                    message_id=msg_id,
                )
                citations_data = nli_result.get("verified_citations", citations_data)
                yield format_sse("citation_verified", {
                    "message_id": msg_id,
                    "status": nli_result.get("status", "VERIFIED"),
                    "average_entailment": nli_result.get("average_entailment", 1.0),
                    "verified_citations": citations_data,
                })
            except Exception as e:
                logger.warning("nli_claim_verification_skipped", error=str(e))

            # Phase 5: Emit completion
            elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            yield format_sse("done", {
                "message_id": msg_id,
                "session_id": str(session_id) if session_id else None,
                "tokens_generated": tokens_count,
                "latency_ms": elapsed_ms,
                "full_text": full_content,
                "citations": citations_data,
            })

        except asyncio.CancelledError:
            logger.info("stream_cancelled_by_runtime", session_id=str(session_id))
            raise
        except Exception as e:
            logger.error("stream_generation_error", error=str(e), session_id=str(session_id))
            yield format_sse("error", {"error": str(e), "code": "STREAM_ERROR"})


phased_stream_generator = PhasedStreamGenerator()
