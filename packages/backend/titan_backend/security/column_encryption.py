import base64
import json
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.types import Text, TypeDecorator
from titan_backend.core.config import settings


class EncryptedField(TypeDecorator):
    """SQLAlchemy TypeDecorator that transparently encrypts field values with AES-256-GCM.

    Format in database: `enc:v1:<nonce_b64>:<ciphertext_b64>`
    """

    impl = Text
    cache_ok = True

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        import hashlib

        key_src = settings.SECRET_KEY or "titanrag-default-column-encryption-key-32b"
        self._key = hashlib.sha256(key_src.encode("utf-8")).digest()

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None

        if isinstance(value, dict | list):
            raw = json.dumps(value).encode("utf-8")
        elif isinstance(value, str):
            raw = value.encode("utf-8")
        else:
            raw = str(value).encode("utf-8")

        aesgcm = AESGCM(self._key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, raw, b"titanrag-column-guard")

        nonce_b64 = base64.b64encode(nonce).decode("ascii")
        ct_b64 = base64.b64encode(ciphertext).decode("ascii")
        return f"enc:v1:{nonce_b64}:{ct_b64}"

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None

        if not isinstance(value, str) or not value.startswith("enc:v1:"):
            return value

        parts = value.split(":")
        if len(parts) != 4:
            return value

        nonce = base64.b64decode(parts[2])
        ciphertext = base64.b64decode(parts[3])

        aesgcm = AESGCM(self._key)
        try:
            decrypted = aesgcm.decrypt(nonce, ciphertext, b"titanrag-column-guard")
            decoded_str = decrypted.decode("utf-8")
            try:
                return json.loads(decoded_str)
            except Exception:
                return decoded_str
        except Exception:
            return "[ENCRYPTED_VALUE_UNREADABLE]"
