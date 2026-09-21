from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.core.dependencies import CurrentUser, get_current_user
from titan_backend.core.errors import ForbiddenError
from titan_backend.db.models.encryption import KmsKeyConfiguration, KmsProviderType
from titan_backend.db.session import get_db
from titan_backend.security.key_rotation import KeyRotationManager
from titan_backend.security.kms import EnvelopeEncryptionService, KmsProviderFactory

router = APIRouter(prefix="/security/kms", tags=["Key Management & BYOK"])


class ConfigureKmsPayload(BaseModel):
    provider: KmsProviderType = KmsProviderType.LOCAL
    key_arn_or_path: str = Field(..., description="KMS Key ARN or HashiCorp Vault transit path")
    rotation_schedule_days: int = Field(90, ge=30, le=365)


class TestEncryptPayload(BaseModel):
    plaintext: str = Field(..., description="Sample plaintext string to encrypt")


class TestDecryptPayload(BaseModel):
    ciphertext: str
    nonce: str


@router.get("", summary="Get Current Tenant KMS Configuration")
async def get_kms_config(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(KmsKeyConfiguration).where(KmsKeyConfiguration.tenant_id == current_user.tenant_id)
    config = (await session.execute(stmt)).scalar_one_or_none()

    if not config:
        return {
            "tenant_id": str(current_user.tenant_id),
            "status": "UNCONFIGURED",
            "provider": KmsProviderType.LOCAL.value,
            "dek_version": 1,
            "is_active": True,
            "note": "Default local AES-256 envelope encryption active.",
        }

    return {
        "tenant_id": str(config.tenant_id),
        "status": "CONFIGURED" if config.is_active else "REVOKED",
        "provider": config.provider.value,
        "key_arn_or_path": config.key_arn_or_path,
        "dek_version": config.dek_version,
        "rotation_schedule_days": config.rotation_schedule_days,
        "is_active": config.is_active,
        "created_at": config.created_at.isoformat(),
        "rotated_at": config.rotated_at.isoformat() if config.rotated_at else None,
    }


@router.post("", summary="Configure BYOK KMS Key")
async def configure_kms(
    payload: ConfigureKmsPayload,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if current_user.role not in ["OWNER", "ADMIN"]:
        raise ForbiddenError("Admin privilege required to configure BYOK KMS")

    provider = KmsProviderFactory.get_provider(payload.provider)
    plain_dek, enc_dek = await provider.generate_data_key(payload.key_arn_or_path)

    stmt = select(KmsKeyConfiguration).where(KmsKeyConfiguration.tenant_id == current_user.tenant_id)
    config = (await session.execute(stmt)).scalar_one_or_none()

    if config:
        config.provider = payload.provider
        config.key_arn_or_path = payload.key_arn_or_path
        config.encrypted_dek = enc_dek
        config.dek_version += 1
        config.rotation_schedule_days = payload.rotation_schedule_days
        config.is_active = True
    else:
        config = KmsKeyConfiguration(
            tenant_id=current_user.tenant_id,
            provider=payload.provider,
            key_arn_or_path=payload.key_arn_or_path,
            encrypted_dek=enc_dek,
            dek_version=1,
            rotation_schedule_days=payload.rotation_schedule_days,
            is_active=True,
        )
        session.add(config)

    await session.commit()
    await session.refresh(config)

    return {
        "tenant_id": str(config.tenant_id),
        "provider": config.provider.value,
        "key_arn_or_path": config.key_arn_or_path,
        "dek_version": config.dek_version,
        "is_active": config.is_active,
        "status": "KMS_CONFIGURED",
    }


@router.post("/rotate", summary="Trigger Zero-Downtime Key Rotation")
async def rotate_kms_key(
    payload: ConfigureKmsPayload | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if current_user.role not in ["OWNER", "ADMIN"]:
        raise ForbiddenError("Admin privilege required to trigger key rotation")

    new_prov = payload.provider if payload else None
    new_arn = payload.key_arn_or_path if payload else None

    return await KeyRotationManager.rotate_tenant_key(
        session=session,
        tenant_id=current_user.tenant_id,
        new_provider=new_prov,
        new_key_arn=new_arn,
    )


@router.post("/revoke", summary="Emergency Cryptographic Revocation")
async def revoke_kms_key(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if current_user.role != "OWNER":
        raise ForbiddenError("Tenant Owner privilege required for emergency cryptographic revocation")

    await EnvelopeEncryptionService.revoke_tenant_key(session, current_user.tenant_id)
    return {
        "tenant_id": str(current_user.tenant_id),
        "status": "KEY_REVOKED",
        "message": "Tenant cryptographic keys revoked. All tenant ciphertext is now indecipherable until restored.",
    }


@router.post("/test-encrypt", summary="Test Round-Trip Envelope Encryption")
async def test_roundtrip_encrypt(
    payload: TestEncryptPayload,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    enc_res = await EnvelopeEncryptionService.encrypt_payload(
        session=session,
        tenant_id=current_user.tenant_id,
        plaintext=payload.plaintext,
    )
    decrypted = await EnvelopeEncryptionService.decrypt_payload(
        session=session,
        tenant_id=current_user.tenant_id,
        ciphertext_b64=enc_res["ciphertext"],
        nonce_b64=enc_res["nonce"],
    )
    return {
        "ciphertext": enc_res["ciphertext"],
        "nonce": enc_res["nonce"],
        "algorithm": enc_res["algorithm"],
        "roundtrip_verified": decrypted.decode("utf-8") == payload.plaintext,
    }
