import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import bcrypt
import jwt

from titan_backend.core.config import settings
from titan_backend.core.errors import AppException


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(
    user_id: UUID | str,
    tenant_id: UUID | str,
    email: str,
    role: str = "MEMBER",
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """
    Generate an access token.
    Returns: (token_str, jti)
    """
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    jti = str(uuid4())
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "email": email,
        "role": role,
        "type": "access",
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)

    key = (
        settings.JWT_PRIVATE_KEY
        if settings.ALGORITHM.startswith("RS") and settings.JWT_PRIVATE_KEY
        else settings.SECRET_KEY
    )
    token = jwt.encode(payload, key, algorithm=settings.ALGORITHM)
    return token, jti


def create_refresh_token(
    user_id: UUID | str,
    tenant_id: UUID | str,
    expires_delta: timedelta | None = None,
) -> tuple[str, str]:
    """
    Generate a long-lived refresh token.
    Returns: (token_str, jti)
    """
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    jti = str(uuid4())
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "type": "refresh",
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    key = (
        settings.JWT_PRIVATE_KEY
        if settings.ALGORITHM.startswith("RS") and settings.JWT_PRIVATE_KEY
        else settings.SECRET_KEY
    )
    token = jwt.encode(payload, key, algorithm=settings.ALGORITHM)
    return token, jti


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.
    """
    key = (
        settings.JWT_PUBLIC_KEY
        if settings.ALGORITHM.startswith("RS") and settings.JWT_PUBLIC_KEY
        else settings.SECRET_KEY
    )
    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=[settings.ALGORITHM],
            options={"require": ["sub", "exp", "iat", "jti"]},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise AppException(
            message="Token has expired",
            status_code=401,
            error_code="TOKEN_EXPIRED",
        ) from None
    except jwt.PyJWTError as e:
        raise AppException(
            message=f"Invalid token: {e}",
            status_code=401,
            error_code="INVALID_TOKEN",
        ) from None


def generate_secure_api_key(prefix: str = "rg_live") -> tuple[str, str, str]:
    """
    Generates a high-entropy API key.
    Returns: (full_plaintext_key, key_prefix, sha256_hash)
    """
    import hashlib

    raw_entropy = secrets.token_urlsafe(32)
    full_key = f"{prefix}_{raw_entropy}"
    key_prefix = full_key[:12]
    hashed_key = hashlib.sha256(full_key.encode("utf-8")).hexdigest()
    return full_key, key_prefix, hashed_key


def hash_api_key(api_key: str) -> str:
    import hashlib

    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()
