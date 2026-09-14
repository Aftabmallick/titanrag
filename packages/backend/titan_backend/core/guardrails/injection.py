import re
import uuid
from typing import NamedTuple

from titan_backend.core.errors import AppException
from titan_backend.core.logging import logger


class PromptInjectionError(AppException):
    def __init__(self, message: str = "Potential prompt injection or adversarial pattern detected.", details: dict | None = None):
        super().__init__(
            status_code=400,
            error_code="PROMPT_INJECTION_DETECTED",
            message=message,
            details=details or {},
        )


class SanitizedQuery(NamedTuple):
    clean_text: str
    canary_token: str
    isolated_prompt_block: str


# High-risk adversarial & jailbreak signature patterns
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|directives|rules)", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions|directives|rules)", re.IGNORECASE),
    re.compile(r"system\s+prompt\s+override", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(DAN|unrestricted|jailbroken|in\s+developer\s+mode)", re.IGNORECASE),
    re.compile(r"reveal\s+(your\s+)?(system\s+prompt|initial\s+instructions|hidden\s+rules)", re.IGNORECASE),
    re.compile(r"repeat\s+(everything|the\s+words)\s+above", re.IGNORECASE),
    re.compile(r"sudo\s+mode|root\s+access|bypass\s+safety", re.IGNORECASE),
    re.compile(r"<\s*\|im_start\|\s*>|<\s*\|im_end\|\s*>", re.IGNORECASE),
    re.compile(r"\[\s*INST\s*\]|\[\s*/INST\s*\]", re.IGNORECASE),
]


def detect_prompt_injection(text: str) -> None:
    """Scans user query for adversarial prompt injection patterns.

    Raises PromptInjectionError if any signature matches.
    """
    if not text:
        return

    for pattern in INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            matched_snippet = match.group(0)
            logger.warning(
                "prompt_injection_threat_detected",
                matched_pattern=pattern.pattern,
                matched_snippet=matched_snippet,
            )
            raise PromptInjectionError(
                details={
                    "threat_type": "PROMPT_INJECTION",
                    "matched_snippet": matched_snippet,
                }
            )


def sanitize_and_isolate_query(query: str) -> SanitizedQuery:
    """Validates, sanitizes, generates a canary token, and wraps query in isolation boundaries."""
    detect_prompt_injection(query)

    # Basic sanitization
    clean_text = query.strip()

    # Generate canary token
    canary_token = f"canary-{uuid.uuid4().hex[:12]}"

    # Delimiter boundary isolation
    isolated_prompt_block = (
        f"===USER QUERY BEGIN (CANARY: {canary_token})===\n"
        f"{clean_text}\n"
        f"===USER QUERY END (CANARY: {canary_token})==="
    )

    return SanitizedQuery(
        clean_text=clean_text,
        canary_token=canary_token,
        isolated_prompt_block=isolated_prompt_block,
    )


def verify_canary_leak(generated_text: str, canary_token: str) -> bool:
    """Returns True if canary token was leaked in assistant generation."""
    if canary_token and canary_token in generated_text:
        logger.error("canary_token_leaked_in_generation", canary=canary_token)
        return True
    return False
