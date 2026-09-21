from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from titan_backend.db.models.encryption import KmsKeyConfiguration, KmsProviderType
from titan_backend.security.column_encryption import EncryptedField
from titan_backend.security.key_rotation import KeyRotationManager
from titan_backend.security.kms import EnvelopeEncryptionService


@pytest.mark.asyncio
async def test_envelope_encryption_roundtrip():
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    tenant_id = uuid4()
    plaintext = "Enterprise Confidential NDA Information 2026"

    # Mock DB query for KmsKeyConfiguration
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_res

    with patch("titan_backend.security.kms.get_redis_client") as mock_redis_getter:
        cache_store = {}
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = lambda k: cache_store.get(k)
        mock_redis.set.side_effect = lambda k, v, **kw: cache_store.update({k: v})
        mock_redis_getter.return_value = mock_redis

        enc_res = await EnvelopeEncryptionService.encrypt_payload(session, tenant_id, plaintext)

        assert "ciphertext" in enc_res
        assert "nonce" in enc_res
        assert enc_res["algorithm"] == "AES-256-GCM"

        decrypted_bytes = await EnvelopeEncryptionService.decrypt_payload(
            session=session,
            tenant_id=tenant_id,
            ciphertext_b64=enc_res["ciphertext"],
            nonce_b64=enc_res["nonce"],
        )

        assert decrypted_bytes.decode("utf-8") == plaintext


@pytest.mark.asyncio
async def test_key_rotation_flow():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    tenant_id = uuid4()
    config = KmsKeyConfiguration(
        id=uuid4(),
        tenant_id=tenant_id,
        provider=KmsProviderType.LOCAL,
        key_arn_or_path="tenant/master",
        encrypted_dek=b"sample_encrypted_dek",
        dek_version=1,
        is_active=True,
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = config
    session.execute.return_value = mock_res

    with patch("titan_backend.security.key_rotation.get_redis_client") as mock_redis_getter:
        mock_redis = AsyncMock()
        mock_redis_getter.return_value = mock_redis

        rotation_res = await KeyRotationManager.rotate_tenant_key(
            session=session,
            tenant_id=tenant_id,
        )

        assert rotation_res["old_dek_version"] == 1
        assert rotation_res["new_dek_version"] == 2
        assert rotation_res["status"] == "ROTATION_SUCCESSFUL"


def test_encrypted_field_type_decorator():
    field = EncryptedField()
    test_dict = {"ssn": "123-45-6789", "salary": 150000}

    # Bind param should produce enc:v1:... ciphertext
    bind_value = field.process_bind_param(test_dict, None)
    assert bind_value is not None
    assert bind_value.startswith("enc:v1:")

    # Result value should decrypt back to original dict
    result_value = field.process_result_value(bind_value, None)
    assert result_value == test_dict
