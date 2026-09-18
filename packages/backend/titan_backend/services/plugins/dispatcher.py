import json
import time
from typing import Any
from uuid import UUID

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from titan_backend.db.base import utc_now
from titan_backend.db.models.plugin import HookType, Plugin, PluginExecutionLog, PluginHealthStatus
from titan_backend.services.plugins.circuit_breaker import PluginCircuitBreaker
from titan_backend.services.plugins.signer import WebhookSigner

logger = structlog.get_logger(__name__)


class PluginDispatchResult:
    def __init__(
        self,
        success: bool,
        status_code: int | None = None,
        data: dict[str, Any] | None = None,
        error: str | None = None,
        latency_ms: float = 0.0,
        circuit_tripped: bool = False,
    ):
        self.success = success
        self.status_code = status_code
        self.data = data or {}
        self.error = error
        self.latency_ms = latency_ms
        self.circuit_tripped = circuit_tripped

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "status_code": self.status_code,
            "data": self.data,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "circuit_tripped": self.circuit_tripped,
        }


class PluginDispatcher:
    """
    High-performance asynchronous dispatcher for TitanRAG webhook micro-hooks.
    Applies cryptographic HMAC signatures, enforces timeout budgets, writes execution logs,
    and isolates the platform via circuit breaker fault tolerance.
    """

    def __init__(self, db: AsyncSession, http_client: httpx.AsyncClient | None = None):
        self.db = db
        self._external_client = http_client

    async def get_active_plugins_for_hook(
        self,
        workspace_id: UUID,
        hook_type: HookType | str,
    ) -> list[Plugin]:
        """Fetch all active, non-tripped plugins registered for a specific hook type."""
        hook_str = hook_type.value if isinstance(hook_type, HookType) else str(hook_type)
        stmt = select(Plugin).where(
            Plugin.workspace_id == workspace_id,
            Plugin.is_active.is_(True),
        )
        res = await self.db.execute(stmt)
        plugins = res.scalars().all()
        # Filter plugins that contain the requested hook_type in their JSON array
        return [p for p in plugins if hook_str in (p.hooks or [])]

    async def dispatch_single(
        self,
        plugin: Plugin,
        hook_type: HookType | str,
        payload: dict[str, Any],
        request_id: str | None = None,
    ) -> PluginDispatchResult:
        """
        Dispatch a micro-hook payload to a single external plugin endpoint.
        """
        hook_str = hook_type.value if isinstance(hook_type, HookType) else str(hook_type)
        can_run = await PluginCircuitBreaker.can_execute(plugin.id)
        if not can_run:
            logger.warning(
                "plugin_dispatch_skipped_circuit_open",
                plugin_id=str(plugin.id),
                plugin_name=plugin.name,
                hook_type=hook_str,
            )
            return PluginDispatchResult(
                success=False,
                error="Circuit breaker is OPEN (service degraded)",
                circuit_tripped=True,
            )

        payload_bytes = json.dumps(payload, default=str).encode("utf-8")
        sig_header, ts = WebhookSigner.sign_payload(
            secret=plugin.webhook_secret,
            payload_bytes=payload_bytes,
        )

        headers = {
            "Content-Type": "application/json",
            "X-Titan-Signature": sig_header,
            "X-Titan-Timestamp": str(ts),
            "X-Titan-Hook": hook_str,
            "X-Titan-Plugin-Id": str(plugin.id),
            "User-Agent": f"TitanRAG-PluginDispatcher/1.0 (Plugin: {plugin.slug})",
        }
        if request_id:
            headers["X-Request-Id"] = request_id

        timeout_sec = max(0.5, float(plugin.timeout_ms) / 1000.0)
        start_time = time.perf_counter()
        status_code: int | None = None
        response_data: dict[str, Any] | None = None
        error_msg: str | None = None
        success = False
        tripped = False

        try:
            client = self._external_client or httpx.AsyncClient(timeout=timeout_sec)
            try:
                resp = await client.post(
                    plugin.endpoint_url,
                    content=payload_bytes,
                    headers=headers,
                )
                status_code = resp.status_code
                if resp.is_success:
                    success = True
                    try:
                        response_data = resp.json()
                    except Exception:
                        response_data = {"raw_text": resp.text}
                else:
                    error_msg = f"HTTP {resp.status_code}: {resp.text[:500]}"
            finally:
                if self._external_client is None:
                    await client.aclose()

        except httpx.TimeoutException:
            error_msg = f"Webhook timeout exceeded ({plugin.timeout_ms}ms)"
        except Exception as e:
            error_msg = f"Webhook connection error: {str(e)}"

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Update circuit breaker and health status
        if success:
            await PluginCircuitBreaker.record_success(plugin.id)
            plugin.failure_count = 0
            plugin.health_status = PluginHealthStatus.HEALTHY
            plugin.circuit_tripped = False
        else:
            tripped = await PluginCircuitBreaker.record_failure(plugin.id)
            plugin.failure_count += 1
            if tripped:
                plugin.circuit_tripped = True
                plugin.circuit_tripped_at = utc_now()
                plugin.health_status = PluginHealthStatus.DEGRADED

        # Record audit log
        try:
            log_entry = PluginExecutionLog(
                tenant_id=plugin.tenant_id,
                workspace_id=plugin.workspace_id,
                plugin_id=plugin.id,
                hook_type=hook_str,
                request_id=request_id,
                status_code=status_code,
                latency_ms=latency_ms,
                request_payload_sample={"keys": list(payload.keys())},
                response_payload_sample=response_data if success else None,
                error_message=error_msg,
                timestamp=utc_now(),
            )
            self.db.add(log_entry)
            await self.db.commit()
        except Exception as log_err:
            logger.warning("failed_saving_plugin_execution_log", error=str(log_err))

        return PluginDispatchResult(
            success=success,
            status_code=status_code,
            data=response_data,
            error=error_msg,
            latency_ms=latency_ms,
            circuit_tripped=tripped,
        )

    async def ping_probe(self, plugin: Plugin) -> PluginDispatchResult:
        """
        Execute an immediate health verification probe to test connectivity and signature.
        """
        ping_payload = {
            "event": "ping",
            "plugin_id": str(plugin.id),
            "workspace_id": str(plugin.workspace_id),
            "timestamp": int(time.time()),
        }
        res = await self.dispatch_single(
            plugin=plugin,
            hook_type="PING",
            payload=ping_payload,
            request_id="ping-probe",
        )
        plugin.last_ping_at = utc_now()
        await self.db.commit()
        return res
