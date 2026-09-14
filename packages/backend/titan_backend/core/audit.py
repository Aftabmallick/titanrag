import functools
from collections.abc import Callable
from typing import Any
from uuid import UUID

import structlog
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.db.models.audit import AuditLog
from titan_backend.db.session import async_session_factory

logger = structlog.get_logger("titanrag.audit")


async def record_audit_event(
    session: AsyncSession,
    tenant_id: UUID,
    user_id: UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """
    Directly persists an event into the tenant's PostgreSQL `audit_log` table.
    """
    try:
        audit_entry = AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
        )
        session.add(audit_entry)
        await session.commit()
        return audit_entry
    except Exception as e:
        logger.warning("record_audit_event_failed", action=action, error=str(e))
        return AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
        )


def audit_action(action: str, resource_type: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator that automatically logs admin/sensitive API actions into `audit_log`.
    Extracts tenant and user context from Request state or dependency kwargs.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)

            try:
                request: Request | None = None
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
                if not request:
                    for val in kwargs.values():
                        if isinstance(val, Request):
                            request = val
                            break

                current_user = kwargs.get("current_user")
                if not current_user and request:
                    current_user = getattr(request.state, "current_user", None)

                tenant_id = getattr(current_user, "tenant_id", None)
                if not tenant_id and request:
                    tenant_id = getattr(request.state, "tenant_id", None)

                user_id = getattr(current_user, "id", None)

                if tenant_id and user_id:
                    ip_address = request.client.host if request and request.client else None
                    resource_id = str(
                        kwargs.get("workspace_id")
                        or kwargs.get("group_id")
                        or kwargs.get("key_id")
                        or kwargs.get("id")
                        or ""
                    )

                    async with async_session_factory() as session:
                        await record_audit_event(
                            session=session,
                            tenant_id=tenant_id,
                            user_id=user_id,
                            action=action,
                            resource_type=resource_type,
                            resource_id=resource_id or None,
                            details={
                                "method": request.method if request else "",
                                "path": request.url.path if request else "",
                            },
                            ip_address=ip_address,
                        )
            except Exception as e:
                logger.warning("audit_decorator_failed", action=action, error=str(e))

            return result

        return wrapper

    return decorator
