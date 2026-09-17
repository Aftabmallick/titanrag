import os
import time
from typing import Any, Protocol

import structlog

logger = structlog.get_logger(__name__)


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
    """Production HashiCorp Vault secret provider with TTL caching and token renewal.

    Falls back cleanly to EnvSecretProvider if Vault is offline or uninitialized.
    """

    def __init__(
        self,
        vault_url: str | None = None,
        vault_token: str | None = None,
        mount_point: str = "secret",
    ):
        self.vault_url = vault_url or os.getenv("VAULT_ADDR", "http://vault:8200")
        self.vault_token = vault_token or os.getenv("VAULT_TOKEN")
        self.mount_point = mount_point
        self._fallback = EnvSecretProvider()
        self._cache: dict[str, tuple[str | None, float]] = {}
        self.ttl = 300
        self._client: Any = None
        self._init_client()

    def _init_client(self) -> None:
        if not self.vault_token:
            logger.info("vault_token_not_set_using_env_fallback")
            return
        try:
            import hvac

            self._client = hvac.Client(url=self.vault_url, token=self.vault_token)
            if not self._client.is_authenticated():
                logger.warning("vault_authentication_failed")
                self._client = None
            else:
                logger.info("vault_client_authenticated", url=self.vault_url)
        except ImportError:
            logger.info("hvac_not_installed_using_env_fallback")
        except Exception as e:
            logger.warning("vault_init_error", error=str(e))

    def get_secret(self, key: str, default: str | None = None) -> str | None:
        now = time.time()
        if key in self._cache:
            val, exp = self._cache[key]
            if now < exp:
                return val

        if self._client:
            try:
                # Vault KV v2 lookup
                secret_resp = self._client.secrets.kv.v2.read_secret_version(
                    path=key,
                    mount_point=self.mount_point,
                )
                data = secret_resp.get("data", {}).get("data", {})
                val = data.get("value") or data.get(key)
                if val is not None:
                    self._cache[key] = (str(val), now + self.ttl)
                    return str(val)
            except Exception as e:
                logger.warning("vault_read_failed_falling_back", key=key, error=str(e))

        val = self._fallback.get_secret(key, default)
        self._cache[key] = (val, now + self.ttl)
        return val


class AwsSecretsManagerProvider:
    """AWS Secrets Manager provider with local caching and environment fallback."""

    def __init__(self, region_name: str | None = None):
        self.region_name = region_name or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        self._fallback = EnvSecretProvider()
        self._cache: dict[str, tuple[str | None, float]] = {}
        self.ttl = 300
        self._client: Any = None
        self._init_client()

    def _init_client(self) -> None:
        try:
            import boto3

            self._client = boto3.client("secretsmanager", region_name=self.region_name)
        except ImportError:
            logger.info("boto3_not_installed_using_env_fallback")
        except Exception as e:
            logger.warning("aws_secrets_init_failed", error=str(e))

    def get_secret(self, key: str, default: str | None = None) -> str | None:
        now = time.time()
        if key in self._cache:
            val, exp = self._cache[key]
            if now < exp:
                return val

        if self._client:
            try:
                resp = self._client.get_secret_value(SecretId=key)
                val = resp.get("SecretString")
                if val is not None:
                    self._cache[key] = (val, now + self.ttl)
                    return val
            except Exception as e:
                logger.warning("aws_secret_lookup_failed", key=key, error=str(e))

        val = self._fallback.get_secret(key, default)
        self._cache[key] = (val, now + self.ttl)
        return val


def _create_secret_provider() -> SecretProvider:
    backend = os.getenv("SECRETS_BACKEND", "env").lower().strip()
    if backend == "vault":
        return VaultSecretProvider()
    elif backend in ("aws", "secretsmanager"):
        return AwsSecretsManagerProvider()
    return EnvSecretProvider()


_provider: SecretProvider = _create_secret_provider()


def get_secret_provider() -> SecretProvider:
    global _provider
    return _provider
