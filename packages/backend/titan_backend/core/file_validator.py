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
    re.compile(rb"EICAR-STANDARD-ANTIVIRUS-TEST-FILE!"),
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


def scan_with_clamav(file_bytes: bytes, host: str, port: int = 3310, timeout: float = 5.0) -> tuple[bool, str | None]:
    """Streams bytes to ClamAV daemon using zINSTREAM protocol.
    Format: 'zINSTREAM\\0' + chunks: [4-byte big-endian length, chunk bytes] + 4-byte 0 length.
    """
    import socket
    import struct

    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall(b"zINSTREAM\0")
            chunk_size = 2048
            for i in range(0, len(file_bytes), chunk_size):
                chunk = file_bytes[i : i + chunk_size]
                sock.sendall(struct.pack(">I", len(chunk)) + chunk)
            sock.sendall(struct.pack(">I", 0))

            response = b""
            while True:
                data = sock.recv(1024)
                if not data:
                    break
                response += data

            resp_str = response.decode("utf-8", errors="ignore").strip()
            # Response format: 'stream: OK' or 'stream: <VirusName> FOUND'
            if "FOUND" in resp_str:
                virus_name = resp_str.replace("stream:", "").replace("FOUND", "").strip()
                return False, virus_name
            return True, None
    except Exception as e:
        logger.warning("clamav_daemon_unreachable_or_failed", host=host, error=str(e))
        return True, None


def scan_file_safety(file_bytes: bytes, filename: str) -> tuple[bool, list[str]]:
    """Scans file content for malicious payload signatures and embedded exploit triggers.
    Supports ClamAV daemon network scanning and pattern heuristic verification.
    Returns: (is_safe, list_of_threat_descriptions)
    """
    from titan_backend.core.config import settings

    threats: list[str] = []

    # 1. ClamAV Daemon scan if configured
    if settings.CLAMAV_HOST:
        is_clamav_clean, virus_name = scan_with_clamav(file_bytes, host=settings.CLAMAV_HOST, port=settings.CLAMAV_PORT)
        if not is_clamav_clean and virus_name:
            threats.append(f"CLAMAV_DETECTED_{virus_name}")

    # 2. Check for executable headers
    if file_bytes.startswith((DOS_PE_MAGIC, ELF_MAGIC)):
        threats.append("MALICIOUS_EXECUTABLE_HEADER")

    # 3. Scan for suspicious command invocation payloads
    for pattern in SUSPICIOUS_PATTERNS:
        if pattern.search(file_bytes):
            threats.append(f"SUSPICIOUS_PAYLOAD_{pattern.pattern.decode('utf-8', errors='ignore')[:30]}")

    is_safe = len(threats) == 0
    if not is_safe:
        logger.warning("security_threat_detected_in_file", filename=filename, threats=threats)

    return is_safe, threats
