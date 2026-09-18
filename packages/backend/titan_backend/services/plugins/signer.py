import hashlib
import hmac
import secrets
import time


class WebhookSigner:
    """
    Cryptographic HMAC-SHA256 signature generator and verifier for TitanRAG
    out-of-process webhook micro-hook plugins.
    Includes replay mitigation via timestamp drift boundaries.
    """

    @staticmethod
    def generate_secret(n_bytes: int = 32) -> str:
        """Generate a cryptographically secure 256-bit hexadecimal secret."""
        return secrets.token_hex(n_bytes)

    @classmethod
    def compute_signature(cls, secret: str, payload_bytes: bytes, timestamp: int) -> str:
        """
        Compute HMAC-SHA256 over '{timestamp}.{payload}'.
        """
        message = f"{timestamp}.".encode() + payload_bytes
        return hmac.new(
            key=secret.encode("utf-8"),
            msg=message,
            digestmod=hashlib.sha256,
        ).hexdigest()

    @classmethod
    def sign_payload(cls, secret: str, payload_bytes: bytes, timestamp: int | None = None) -> tuple[str, int]:
        """
        Sign a webhook payload and format header value: 't={timestamp},v1={hex_hash}'.
        Returns (header_value, timestamp).
        """
        ts = int(time.time()) if timestamp is None else timestamp
        digest = cls.compute_signature(secret=secret, payload_bytes=payload_bytes, timestamp=ts)
        header_val = f"t={ts},v1={digest}"
        return header_val, ts

    @classmethod
    def verify_signature(
        cls,
        secret: str,
        payload_bytes: bytes,
        header_value: str,
        max_drift_seconds: int = 300,
        current_time: int | None = None,
    ) -> bool:
        """
        Verify incoming webhook signature header 't={timestamp},v1={hex_hash}'.
        Mitigates replay attacks by checking timestamp drift <= max_drift_seconds (default 5 min).
        """
        if not header_value:
            return False

        pairs: dict[str, str] = {}
        for part in header_value.split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                pairs[k.strip()] = v.strip()

        if "t" not in pairs or "v1" not in pairs:
            return False

        try:
            ts = int(pairs["t"])
        except ValueError:
            return False

        now = int(time.time()) if current_time is None else current_time
        if abs(now - ts) > max_drift_seconds:
            # Replay attack or excessive clock drift
            return False

        expected = cls.compute_signature(secret=secret, payload_bytes=payload_bytes, timestamp=ts)
        return hmac.compare_digest(expected, pairs["v1"])
