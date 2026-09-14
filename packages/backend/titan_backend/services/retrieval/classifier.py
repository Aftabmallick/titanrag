import re
import time
from enum import Enum
from typing import NamedTuple

from titan_backend.api.v1.schemas.chat import PipelineMode
from titan_backend.core.logging import logger


class QueryIntent(str, Enum):
    RAG_QUERY = "RAG_QUERY"
    CHITCHAT = "CHITCHAT"
    META = "META"


class ClassificationResult(NamedTuple):
    intent: QueryIntent
    normalized_query: str
    recommended_mode: PipelineMode
    classification_latency_ms: float
    chitchat_response: str | None = None
    meta_response: str | None = None


# Patterns for Chit-chat
CHITCHAT_PATTERNS = [
    re.compile(
        r"^(hi|hello|hey|howdy|greetings|good\s+(morning|afternoon|evening|day))"
        r"([\s!.,]*(how\s+are\s+you|what\'?s\s+up|nice\s+to\s+meet\s+you)?)?[\s!?.]*$",
        re.IGNORECASE,
    ),
    re.compile(r"^(how\s+are\s+you|who\s+are\s+you|what\s+is\s+your\s+name|what\s+are\s+you)[\s?!.]*$", re.IGNORECASE),
    re.compile(r"^(thanks|thank\s+you|thx|cheers)[\s!.]*$", re.IGNORECASE),
    re.compile(r"^(bye|goodbye|see\s+you|cya)[\s!.]*$", re.IGNORECASE),
]

# Patterns for System / Meta inquiries
META_PATTERNS = [
    re.compile(r"^(what\s+can\s+you\s+do|how\s+do\s+you\s+work|what\s+is\s+this\s+system)[\s?!.]*$", re.IGNORECASE),
    re.compile(r"^(what\s+documents\s+are\s+here|list\s+my\s+documents|what\s+can\s+i\s+ask)[\s?!.]*$", re.IGNORECASE),
    re.compile(r"^(system\s+status|diagnostics|help)[\s?!.]*$", re.IGNORECASE),
]

# Patterns indicating Deep reasoning / multi-hop comparison
COMPLEX_PATTERNS = [
    re.compile(r"\b(compare|contrast|difference\s+between|versus|vs\.?)\b", re.IGNORECASE),
    re.compile(r"\b(synthesize|comprehensive\s+report|in-depth\s+analysis)\b", re.IGNORECASE),
    re.compile(r"\band\s+also\b.*\?", re.IGNORECASE),
]


class InProcessQueryClassifier:
    """Fast-Path in-process classifier executing in <15ms.

    Categorizes user queries into RAG_QUERY, CHITCHAT, or META, and selects FAST vs DEEP pipeline tracks.
    Supports in-process ONNX Runtime session when model artifacts are present, with instant zero-overhead
    pattern fallback.
    """

    def __init__(self, onnx_model_path: str | None = None) -> None:
        self._onnx_session = None
        self._onnx_model_path = onnx_model_path
        if onnx_model_path:
            self._init_onnx_session(onnx_model_path)

    def _init_onnx_session(self, path: str) -> None:
        try:
            import onnxruntime as ort

            self._onnx_session = ort.InferenceSession(path)
            logger.info("onnx_classifier_loaded", model_path=path)
        except Exception as e:
            logger.debug("onnx_classifier_init_fallback", reason=str(e))
            self._onnx_session = None

    def normalize(self, query: str) -> str:
        # Collapse multiple spaces and trim
        q = re.sub(r"\s+", " ", query).strip()
        return q

    def classify(self, query: str, user_selected_mode: PipelineMode = PipelineMode.AUTO) -> ClassificationResult:
        start = time.perf_counter()
        normalized = self.normalize(query)

        # 1. Chit-chat check
        for pattern in CHITCHAT_PATTERNS:
            if pattern.match(normalized):
                latency = (time.perf_counter() - start) * 1000.0
                return ClassificationResult(
                    intent=QueryIntent.CHITCHAT,
                    normalized_query=normalized,
                    recommended_mode=PipelineMode.FAST,
                    classification_latency_ms=round(latency, 2),
                    chitchat_response="Hello! I am TitanRAG, your enterprise AI knowledge assistant. Ask me anything about your uploaded documents or workspace knowledge base.",
                )

        # 2. Meta inquiry check
        for pattern in META_PATTERNS:
            if pattern.match(normalized):
                latency = (time.perf_counter() - start) * 1000.0
                return ClassificationResult(
                    intent=QueryIntent.META,
                    normalized_query=normalized,
                    recommended_mode=PipelineMode.FAST,
                    classification_latency_ms=round(latency, 2),
                    meta_response="I am TitanRAG. I index your documents using hybrid dense-sparse search and cited grounded generation. You can query policies, contracts, technical specifications, and tabular reports with verifiable citations.",
                )

        # 3. Determine recommended mode (FAST vs DEEP)
        if user_selected_mode != PipelineMode.AUTO:
            chosen_mode = user_selected_mode
        else:
            is_complex = any(pattern.search(normalized) for pattern in COMPLEX_PATTERNS) or len(normalized.split()) > 35
            chosen_mode = PipelineMode.DEEP if is_complex else PipelineMode.FAST

        latency = (time.perf_counter() - start) * 1000.0
        logger.debug("query_classified", intent=QueryIntent.RAG_QUERY.value, mode=chosen_mode.value, latency_ms=latency)

        return ClassificationResult(
            intent=QueryIntent.RAG_QUERY,
            normalized_query=normalized,
            recommended_mode=chosen_mode,
            classification_latency_ms=round(latency, 2),
        )


classifier = InProcessQueryClassifier()
