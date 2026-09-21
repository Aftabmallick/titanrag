import pytest
from titan_backend.core.errors import AppException
from titan_backend.security.file_validator import FileSecurityValidator
from titan_backend.security.scanner import EICAR_SIGNATURE, ClamAVScanner


def test_file_validator_valid_pdf():
    valid_pdf = b"%PDF-1.4\n1 0 obj\n<< /Title (Test) >>\nendobj\ntrailer\n<< >>\n%%EOF"
    res = FileSecurityValidator.validate_file_content("document.pdf", valid_pdf)
    assert res["is_clean"] is True
    assert res["detected_type"] == "pdf"


def test_file_validator_executable_blocked():
    fake_exe = b"MZ\x90\x00\x03\x00\x00\x00"  # Windows PE header
    with pytest.raises(AppException) as exc_info:
        FileSecurityValidator.validate_file_content("payload.pdf", fake_exe)
    assert "Disallowed executable signature" in str(exc_info.value)


def test_file_validator_polyglot_blocked():
    # PDF with ZIP archive injected
    polyglot = b"%PDF-1.4\n" + (b"A" * 1500) + b"PK\x03\x04embedded_archive.zip"
    with pytest.raises(AppException) as exc_info:
        FileSecurityValidator.validate_file_content("polyglot.pdf", polyglot)
    assert "Polyglot attack detected" in str(exc_info.value)


def test_file_validator_anti_xxe():
    xxe_payload = (
        b'<?xml version="1.0"?><!DOCTYPE root [<!ENTITY test SYSTEM "file:///etc/passwd">]><root>&test;</root>'
    )
    with pytest.raises(AppException) as exc_info:
        FileSecurityValidator.validate_file_content("vector.svg", xxe_payload)
    assert "XML External Entity (XXE)" in str(exc_info.value)


def test_file_validator_pdf_launch_action_blocked():
    malicious_pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Action /S /Launch /F (cmd.exe) >>\nendobj\n%%EOF"
    with pytest.raises(AppException) as exc_info:
        FileSecurityValidator.validate_file_content("exploit.pdf", malicious_pdf)
    assert "Potentially malicious PDF action trigger" in str(exc_info.value)


@pytest.mark.asyncio
async def test_clamav_eicar_detection():
    scanner = ClamAVScanner(host="127.0.0.1", port=9999, timeout=0.5)
    res = await scanner.scan_bytes(EICAR_SIGNATURE)
    assert res.is_clean is False
    assert res.quarantined is True
    assert res.threat_name == "EICAR_STANDARD_TEST_VIRUS"
