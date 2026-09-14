import re

import structlog

logger = structlog.get_logger("titanrag.security.file_validator")

# Magic signatures
PDF_MAGIC = b"%PDF"
ZIP_MAGIC = b"PK\x03\x04"
DOS_PE_MAGIC = b"MZ"
ELF_MAGIC = b"\x7fELF"

# Suspicious malicious strings in non-executable files
SUSPICIOUS_PATTERNS = [
    re.compile(rb"(?i)powershell\s+-(?:enc|encodedcommand|nop)"),
    re.compile(rb"(?i)cmd(?:\.exe)?\s+/c"),
    re.compile(rb"(?i)wscript\.shell"),
    re.compile(rb"(?i)eval\s*\(\s*base64_decode"),
    re.compile(rb"(?i)<script[^>]*>.*?eval\(", re.DOTALL),
]


def validate_file_signature(file_bytes: bytes, filename: str) -> tuple[bool, str]:
    """
    Validates file integrity against magic byte signatures.
    Rejects disguised executables (PE, ELF) regardless of file extension.
    Returns: (is_valid, detected_type_or_error)
    """
    if not file_bytes:
        return False, "Empty file"

    header = file_bytes[:16]

    # 1. Immediate rejection of executable binary signatures
    if header.startswith(DOS_PE_MAGIC):
        return False, "Disguised Windows executable (MZ header detected)"
    if header.startswith(ELF_MAGIC):
        return False, "Disguised Linux executable (ELF header detected)"

    lower_fn = filename.lower()

    # 2. PDF validation
    if lower_fn.endswith(".pdf"):
        if not file_bytes.startswith(PDF_MAGIC):
            return False, "Invalid PDF header: Missing %PDF- signature"
        return True, "application/pdf"

    # 3. Office OpenXML & ZIP validation
    if lower_fn.endswith((".docx", ".pptx", ".xlsx", ".zip")):
        if not file_bytes.startswith(ZIP_MAGIC):
            return False, "Invalid archive/Office header: Missing PK signature"
        return True, "application/zip"

    # 4. Text/CSV/Markdown validation (ensure no binary null bytes)
    if lower_fn.endswith((".txt", ".md", ".csv", ".tsv", ".json")):
        sample = file_bytes[:1024]
        if b"\x00" in sample:
            return False, "Binary data detected in text file"
        try:
            sample.decode("utf-8")
        except UnicodeDecodeError:
            return False, "Invalid non-UTF8 encoding in text document"
        return True, "text/plain"

    # Generic binary/document allowed if not an executable
    return True, "application/octet-stream"


def scan_file_safety(file_bytes: bytes, filename: str) -> tuple[bool, list[str]]:
    """
    Scans file content for malicious payload signatures and embedded exploit triggers.
    Returns: (is_safe, list_of_threat_descriptions)
    """
    threats: list[str] = []

    # Check for executable headers
    if file_bytes.startswith((DOS_PE_MAGIC, ELF_MAGIC)):
        threats.append("MALICIOUS_EXECUTABLE_HEADER")

    # Scan for suspicious command invocation payloads
    for pattern in SUSPICIOUS_PATTERNS:
        if pattern.search(file_bytes):
            threats.append(f"SUSPICIOUS_PAYLOAD_{pattern.pattern.decode('utf-8', errors='ignore')[:30]}")

    is_safe = len(threats) == 0
    if not is_safe:
        logger.warning("security_threat_detected_in_file", filename=filename, threats=threats)

    return is_safe, threats
