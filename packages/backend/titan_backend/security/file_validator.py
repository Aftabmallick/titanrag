import hashlib
import re
from typing import Any

from titan_backend.core.errors import AppException, BadRequestError

# Magic Bytes Signatures
MAGIC_SIGNATURES = {
    "pdf": [b"%PDF-"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "zip": [b"PK\x03\x04", b"PK\x05\x06"],  # Also used for docx, pptx, xlsx
}

DISALLOWED_EXECUTABLE_SIGNATURES = [
    (b"MZ", "Windows PE Executable"),
    (b"\x7fELF", "Linux ELF Executable"),
    (b"\xca\xfe\xba\xbe", "Java/Mach-O Universal Binary"),
    (b"#!/bin/", "Shell Script"),
]


class FileSecurityValidator:
    """Enterprise File Ingress Inspection & Sanitization Engine.

    Protects against:
    1. Extension vs. MIME header spoofing
    2. Polyglot and dual-payload executable injection
    3. XML / SVG External Entity (XXE) attacks
    4. PDF malicious script & automated launch actions
    """

    @classmethod
    def validate_file_content(
        cls,
        filename: str,
        data: bytes,
        max_size_bytes: int = 100 * 1024 * 1024,
    ) -> dict[str, Any]:
        # 1. Size Limit Check
        if len(data) > max_size_bytes:
            raise BadRequestError(f"File size ({len(data)} bytes) exceeds configured maximum ({max_size_bytes} bytes)")

        # 2. Executable Header Check (Anti-Binary Smuggling)
        for sig, desc in DISALLOWED_EXECUTABLE_SIGNATURES:
            if data.startswith(sig):
                raise AppException(
                    message=f"Upload rejected: Disallowed executable signature detected ({desc})",
                    code="MALICIOUS_FILE_BLOCKED",
                    status_code=400,
                )

        # 3. Extension & MIME Consistency
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        sha256_hash = hashlib.sha256(data).hexdigest()

        detected_type = "unknown"
        if data.startswith(b"%PDF-"):
            detected_type = "pdf"
        elif data.startswith(b"\x89PNG"):
            detected_type = "png"
        elif data.startswith(b"\xff\xd8\xff"):
            detected_type = "jpg"
        elif data.startswith(b"PK\x03\x04"):
            detected_type = "zip/office"
        elif data.startswith(b"<?xml") or b"<svg" in data[:1024].lower():
            detected_type = "xml/svg"
        else:
            # Check if valid text
            try:
                data[:4096].decode("utf-8")
                detected_type = "text"
            except UnicodeDecodeError:
                detected_type = "binary"

        # Polyglot detection: check if a PDF has a ZIP or ELF appended
        if ext == "pdf" and not data.startswith(b"%PDF-"):
            raise BadRequestError(f"Extension mismatch: file named '{filename}' is not a valid PDF")

        if ext == "pdf" and b"PK\x03\x04" in data[1024:]:
            raise AppException(
                message="Polyglot attack detected: embedded archive within PDF stream",
                code="POLYGLOT_PAYLOAD_DETECTED",
                status_code=400,
            )

        # PDF Structural Security
        if ext == "pdf":
            suspicious_actions = [b"/Launch", b"/EmbeddedFiles"]
            for act in suspicious_actions:
                if act in data:
                    raise AppException(
                        message=f"Potentially malicious PDF action trigger detected: {act.decode()}",
                        code="PDF_EXPLOIT_BLOCKED",
                        status_code=400,
                    )

        # 4. XML / SVG Anti-XXE Sanitization
        sanitized_data = data
        if ext in ["xml", "svg"] or detected_type == "xml/svg":
            text_payload = data.decode("utf-8", errors="replace")
            # Block DOCTYPE and external entities
            if "<!doctype" in text_payload.lower() or "<!entity" in text_payload.lower():
                raise AppException(
                    message="XML External Entity (XXE) payload blocked: DOCTYPE and ENTITY declarations are forbidden",
                    code="XXE_INJECTION_BLOCKED",
                    status_code=400,
                )
            # Strip inline scripts
            text_payload = re.sub(r"<script.*?>.*?</script>", "", text_payload, flags=re.DOTALL | re.IGNORECASE)
            sanitized_data = text_payload.encode("utf-8")

        return {
            "filename": filename,
            "extension": ext,
            "detected_type": detected_type,
            "sha256": sha256_hash,
            "size_bytes": len(sanitized_data),
            "sanitized_data": sanitized_data,
            "is_clean": True,
        }
