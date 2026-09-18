import re
from typing import Any
import structlog

logger = structlog.get_logger("titanrag.retrieval.cross_lingual")

# Language script mapping and common stop-word heuristics
LANGUAGE_PROFILES = {
    "en": {"name": "English", "e5_prefix": "query: "},
    "es": {"name": "Spanish", "e5_prefix": "query: "},
    "de": {"name": "German", "e5_prefix": "query: "},
    "fr": {"name": "French", "e5_prefix": "query: "},
    "ja": {"name": "Japanese", "e5_prefix": "query: "},
    "zh": {"name": "Chinese", "e5_prefix": "query: "},
    "ar": {"name": "Arabic", "e5_prefix": "query: "},
    "ru": {"name": "Russian", "e5_prefix": "query: "},
    "pt": {"name": "Portuguese", "e5_prefix": "query: "},
    "it": {"name": "Italian", "e5_prefix": "query: "},
}

MULTILINGUAL_E5_MODEL = "intfloat/multilingual-e5-large"


class CrossLingualRetriever:
    """
    Coordinates cross-lingual RAG by:
    1. Detecting query language and script.
    2. Generating cross-lingual query expansions (scaffolded translation).
    3. Applying E5 multilingual formatting prefixes ("query: " vs "passage: ").
    4. Enabling zero-shot cross-lingual retrieval across heterogenous language knowledge bases.
    """

    def __init__(self, target_embedding_model: str = MULTILINGUAL_E5_MODEL):
        self.target_embedding_model = target_embedding_model

    def detect_language(self, query: str) -> str:
        """
        Detects language based on unicode script and common language markers.
        """
        q = query.strip()
        if not q:
            return "en"

        # Japanese Hiragana/Katakana
        if re.search(r"[\u3040-\u309f\u30a0-\u30ff]", q):
            return "ja"
        # Chinese Hanzi
        if re.search(r"[\u4e00-\u9fff]", q):
            return "zh"
        # Arabic
        if re.search(r"[\u0600-\u06ff]", q):
            return "ar"
        # Cyrillic (Russian)
        if re.search(r"[\u0400-\u04ff]", q):
            return "ru"

        # Latin heuristics
        lower_q = q.lower()
        words = set(re.findall(r"\b\w+\b", lower_q))

        if words & {"el", "la", "los", "las", "de", "en", "para", "por", "como", "cuál", "cómo"}:
            return "es"
        if words & {"der", "die", "das", "und", "für", "mit", "nicht", "wie", "welche"}:
            return "de"
        if words & {"le", "la", "les", "du", "des", "pour", "avec", "dans", "comment"}:
            return "fr"
        if words & {"um", "uma", "para", "com", "não", "como", "quais"}:
            return "pt"
        if words & {"il", "la", "per", "con", "non", "come", "quali"}:
            return "it"

        return "en"

    def format_e5_query(self, query: str) -> str:
        """
        E5 models require queries to be prefixed with 'query: ' for optimal semantic alignment.
        """
        clean = query.strip()
        if not clean.startswith("query: "):
            return f"query: {clean}"
        return clean

    def format_e5_passage(self, passage: str) -> str:
        """
        E5 models require passages to be prefixed with 'passage: '.
        """
        clean = passage.strip()
        if not clean.startswith("passage: "):
            return f"passage: {clean}"
        return clean

    def scaffold_cross_lingual_queries(
        self,
        query: str,
        detected_lang: str | None = None,
    ) -> list[dict[str, str]]:
        """
        Creates query variants including native language and cross-lingual English search scaffolding.
        """
        lang = detected_lang or self.detect_language(query)
        queries = [
            {
                "language": lang,
                "query": query,
                "e5_formatted": self.format_e5_query(query),
                "is_original": True,
            }
        ]

        # If non-English, provide cross-lingual scaffold
        if lang != "en":
            queries.append(
                {
                    "language": "en",
                    "query": f"[Cross-Lingual Search] {query}",
                    "e5_formatted": self.format_e5_query(query),
                    "is_original": False,
                }
            )

        return queries
