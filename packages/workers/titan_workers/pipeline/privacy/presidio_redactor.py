import hashlib
import re
from typing import Any

import structlog

logger = structlog.get_logger("titanrag.privacy.redactor")

# Robust regex patterns for high-precision PII detection
PATTERNS = {
    "US_SSN": re.compile(r"\b\d{3}[-–\s]?\d{2}[-–\s]?\d{4}\b"),
    "EMAIL_ADDRESS": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"),
    "PHONE_NUMBER": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "CREDIT_CARD": re.compile(r"\b(?:\d{4}[-–\s]?){3}\d{4}\b"),
    "IP_ADDRESS": re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"),
    "US_BANK_NUMBER": re.compile(r"(?i)\b(?:account|acct|routing|bank)[\s#:]*(\d{8,17})\b"),
    "PERSON": re.compile(r"\b(?:Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b"),
}


class PIIRedactor:
    """
    Enterprise PII Redaction Engine supporting REPLACE, HASH, MASK, and OFF modes.
    Incorporates Microsoft Presidio integration with zero-dependency high-precision regex engine.
    """

    def __init__(self, default_mode: str = "REPLACE"):
        self.default_mode = default_mode.upper()
        self._analyzer: Any = None
        self._anonymizer: Any = None

        # Attempt to load Microsoft Presidio if present in environment
        try:
            from presidio_analyzer import AnalyzerEngine  # type: ignore
            from presidio_anonymizer import AnonymizerEngine  # type: ignore

            self._analyzer = AnalyzerEngine()
            self._anonymizer = AnonymizerEngine()
            logger.info("presidio_analyzer_loaded")
        except Exception:
            logger.debug("presidio_not_available_using_regex_engine")

    def _mask_value(self, val: str, entity_type: str) -> str:
        if len(val) <= 4:
            return "***"
        if entity_type == "EMAIL_ADDRESS" and "@" in val:
            name, domain = val.split("@", 1)
            return f"{name[0]}***@{domain}"
        return val[:2] + "*" * (len(val) - 4) + val[-2:]

    def _hash_value(self, val: str) -> str:
        sha = hashlib.sha256(val.encode("utf-8")).hexdigest()[:8]
        return f"[HASH:{sha}]"

    def redact(self, text: str, mode: str | None = None) -> tuple[str, list[dict[str, Any]]]:
        active_mode = (mode or self.default_mode).upper()
        if active_mode == "OFF":
            return text, []

        redacted_text = text
        detected_entities: list[dict[str, Any]] = []

        # If Presidio engines are loaded, use them
        if self._analyzer and self._anonymizer and active_mode == "REPLACE":
            try:
                analyzer_results = self._analyzer.analyze(text=text, language="en")
                if analyzer_results:
                    anonymized_result = self._anonymizer.anonymize(
                        text=text,
                        analyzer_results=analyzer_results,
                    )
                    return anonymized_result.text, [
                        {
                            "type": r.entity_type,
                            "mode": active_mode,
                            "start": r.start,
                            "end": r.end,
                        }
                        for r in analyzer_results
                    ]
            except Exception as e:
                logger.warning("presidio_analysis_failed_fallback_to_regex", error=str(e))

        # Precision regex engine
        for entity_type, pattern in PATTERNS.items():
            matches = list(pattern.finditer(redacted_text))
            for match in reversed(matches):
                val = match.group(0)
                start, end = match.span()

                if active_mode == "REPLACE":
                    replacement = f"[{entity_type}]"
                elif active_mode == "HASH":
                    replacement = self._hash_value(val)
                elif active_mode == "MASK":
                    replacement = self._mask_value(val, entity_type)
                else:
                    replacement = f"[{entity_type}]"

                redacted_text = redacted_text[:start] + replacement + redacted_text[end:]
                detected_entities.append(
                    {
                        "type": entity_type,
                        "mode": active_mode,
                        "start": start,
                        "end": end,
                    }
                )

        return redacted_text, detected_entities
