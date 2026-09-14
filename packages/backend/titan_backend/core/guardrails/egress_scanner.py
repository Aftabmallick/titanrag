import re
from typing import NamedTuple

from titan_backend.core.logging import logger


class ScanResult(NamedTuple):
    clean_chunk: str
    leak_detected: bool
    leak_type: str | None


# High-risk secret and PII patterns for egress scanning
LEAK_PATTERNS = [
    ("TITAN_API_KEY", re.compile(r"rg_[a-zA-Z0-9_-]{24,}")),
    ("OPENAI_API_KEY", re.compile(r"sk-[a-zA-Z0-9_-]{20,}")),
    ("GITHUB_TOKEN", re.compile(r"ghp_[a-zA-Z0-9]{36}")),
    ("AWS_ACCESS_KEY", re.compile(r"\b(AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b")),
    ("PRIVATE_KEY", re.compile(r"-----BEGIN (RSA|EC|OPENSSH|DSA|PGP)?\s?PRIVATE KEY-----")),
    ("US_SSN", re.compile(r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")),
    (
        "CREDIT_CARD",
        re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b"),
    ),
]

# Patterns for partial prefixes at chunk boundaries to prevent token split leakage
POTENTIAL_PREFIX_PATTERNS = [
    re.compile(r"rg_[a-zA-Z0-9_-]*$", re.IGNORECASE),
    re.compile(r"sk-[a-zA-Z0-9_-]*$", re.IGNORECASE),
    re.compile(r"ghp_[a-zA-Z0-9]*$", re.IGNORECASE),
    re.compile(r"\b(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]*$", re.IGNORECASE),
    re.compile(r"-{1,5}(?:BEGIN)?(?:\s[A-Z]*)?$", re.IGNORECASE),
    re.compile(r"\b\d{3}(?:-\d{0,2})?$"),
    re.compile(r"\b(?:\d{4}[-\s]?){1,3}\d{0,4}$"),
]


class StreamingEgressScanner:
    """Maintains a rolling character buffer across streamed token chunks to detect secrets and PII
    even if they span chunk boundaries, using lookahead buffering.
    """

    def __init__(self, window_size: int = 256, max_hold_size: int = 40):
        self.window_size = window_size
        self.max_hold_size = max_hold_size
        self.buffer = ""
        self.total_scanned_chars = 0

    def scan_chunk(self, chunk: str) -> ScanResult:
        """Appends chunk to rolling window, scans for secret patterns, redacts if matched,
        holds back partial prefix tails, and returns the safe-to-emit chunk string.
        """
        if not chunk:
            return ScanResult(clean_chunk="", leak_detected=False, leak_type=None)

        self.buffer += chunk
        self.total_scanned_chars += len(chunk)

        leak_detected = False
        leak_type = None

        # 1. Scan for complete secret patterns
        for name, pattern in LEAK_PATTERNS:
            match = pattern.search(self.buffer)
            while match:
                leak_detected = True
                leak_type = name
                matched_text = match.group(0)
                logger.error("egress_secret_leak_blocked", leak_type=name, length=len(matched_text))
                redacted_placeholder = f"[REDACTED_{name}]"
                self.buffer = self.buffer[: match.start()] + redacted_placeholder + self.buffer[match.end() :]
                match = pattern.search(self.buffer)

        # 2. Check if tail contains a partial prefix that might be completed in the next chunk
        hold_count = 0
        for prefix_pat in POTENTIAL_PREFIX_PATTERNS:
            m = prefix_pat.search(self.buffer)
            if m:
                tail_len = len(self.buffer) - m.start()
                if tail_len <= self.max_hold_size:
                    hold_count = max(hold_count, tail_len)

        if hold_count > 0:
            to_emit = self.buffer[:-hold_count]
            self.buffer = self.buffer[-hold_count:]
        else:
            to_emit = self.buffer
            self.buffer = ""

        # Trim buffer to window size to keep memory bounded
        if len(self.buffer) > self.window_size:
            extra = len(self.buffer) - self.window_size
            to_emit += self.buffer[:extra]
            self.buffer = self.buffer[extra:]

        return ScanResult(clean_chunk=to_emit, leak_detected=leak_detected, leak_type=leak_type)

    def flush(self) -> str:
        """Flushes any remaining held buffer at the end of the stream after final scan."""
        remaining = self.buffer
        self.buffer = ""
        for name, pattern in LEAK_PATTERNS:
            match = pattern.search(remaining)
            while match:
                redacted_placeholder = f"[REDACTED_{name}]"
                remaining = remaining[: match.start()] + redacted_placeholder + remaining[match.end() :]
                match = pattern.search(remaining)
        return remaining
