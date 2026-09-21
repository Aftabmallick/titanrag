from uuid import uuid4

import pytest
from titan_backend.core.errors import ForbiddenError
from titan_backend.security.kms import LocalKmsProvider
from titan_backend.security.scanner import EICAR_SIGNATURE, ClamAVScanner
from titan_backend.security.zdr import ZdrEnforcementProxy


@pytest.mark.asyncio
async def test_clamav_scanner_offline_fallback():
    """Verifies ClamAV scanner degrades gracefully when daemon port is unreachable."""
    scanner = ClamAVScanner(host="127.0.0.1", port=9999, timeout=0.5)
    clean_bytes = b"%PDF-1.4 sample safe pdf content"
    result = await scanner.scan_bytes(clean_bytes)

    assert result.is_clean is True
    assert "Fallback" in result.engine


@pytest.mark.asyncio
async def test_clamav_eicar_virus_quarantine():
    """Verifies that malicious EICAR signature is detected immediately without socket delay."""
    scanner = ClamAVScanner(host="127.0.0.1", port=9999, timeout=0.5)
    result = await scanner.scan_bytes(EICAR_SIGNATURE)

    assert result.is_clean is False
    assert result.threat_name == "EICAR_STANDARD_TEST_VIRUS"
    assert result.quarantined is True


@pytest.mark.asyncio
async def test_kms_local_envelope_encryption_roundtrip():
    """Verifies local KMS provider encrypts and decrypts with AES-256-GCM."""
    provider = LocalKmsProvider("test-master-secret-key-32b-length")
    path = "tenant/test/key"
    plain_dek, enc_dek = await provider.generate_data_key(path)

    assert len(plain_dek) == 32
    assert plain_dek != enc_dek

    decrypted_dek = await provider.decrypt_dek(path, enc_dek)
    assert decrypted_dek == plain_dek


def test_zdr_enforcement_proxy():
    """Verifies ZDR policy blocks non-certified LLM endpoints when enterprise mode is active."""
    tenant_id = uuid4()

    # Certified model -> should allow
    res = ZdrEnforcementProxy.enforce_zdr_policy(tenant_id, "azure/gpt-4o", enforce_zdr=True)
    assert res["decision"] == "ALLOWED"

    # Non-certified consumer model -> should raise ForbiddenError
    with pytest.raises(ForbiddenError) as exc_info:
        ZdrEnforcementProxy.enforce_zdr_policy(tenant_id, "untrusted-consumer-llm-v1", enforce_zdr=True)
    assert "Zero Data Retention (ZDR) policy violation" in str(exc_info.value)

    # If ZDR not enforced, allows with log
    unrestricted = ZdrEnforcementProxy.enforce_zdr_policy(tenant_id, "untrusted-consumer-llm-v1", enforce_zdr=False)
    assert unrestricted["decision"] == "ALLOWED"
