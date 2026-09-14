import os
import time
from typing import Protocol


class SecretProvider(Protocol):
    def get_secret(self, key: str, default: str | None = None) -> str | None: ...


class EnvSecretProvider:
    """Environment-based secret provider for local development."""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[str | None, float]] = {}
        self.ttl = 300  # 5 minutes

    def get_secret(self, key: str, default: str | None = None) -> str | None:
        now = time.time()
        if key in self._cache:
            val, exp = self._cache[key]
            if now < exp:
                return val

        val = os.getenv(key, default)
        self._cache[key] = (val, now + self.ttl)
        return val


class VaultSecretProvider:
    """Production Vault / Cloud KMS stub for enterprise secret injection."""

    def __init__(self, vault_url: str | None = None):
        self.vault_url = vault_url or os.getenv("VAULT_ADDR", "http://vault:8200")
        self._fallback = EnvSecretProvider()

    def get_secret(self, key: str, default: str | None = None) -> str | None:
        # Falls back to environment if Vault is not initialized
        return self._fallback.get_secret(key, default)


_provider: SecretProvider = EnvSecretProvider()


def get_secret_provider() -> SecretProvider:
    global _provider
    return _provider
