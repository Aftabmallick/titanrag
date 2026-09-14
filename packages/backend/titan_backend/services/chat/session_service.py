import uuid
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from titan_backend.api.v1.schemas.chat import (
    ChatMessageResponse,
    ChatSessionResponse,
    CitationPayload,
)
from titan_backend.clients.litellm_client import litellm_client
from titan_backend.clients.redis_client import get_redis_client
from titan_backend.core.errors import AppException
from titan_backend.core.logging import logger
from titan_backend.db.models.chat import ChatMessage, ChatSession, MessageRole


class ChatSessionService:
    """Handles ChatSession and ChatMessage database operations, auto-titling, export, and sharing."""

    async def create_session(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
        title: str = "New Chat",
        meta: dict[str, Any] | None = None,
    ) -> ChatSessionResponse:
        sess_id = uuid.uuid4()
        session = ChatSession(
            id=sess_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            user_id=user_id,
            title=title,
            meta=meta or {},
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

        return ChatSessionResponse(
            id=session.id or sess_id,
            tenant_id=session.tenant_id,
            workspace_id=session.workspace_id,
            user_id=session.user_id,
            title=session.title,
            created_at=session.created_at.isoformat() if session.created_at else "2026-09-14T00:00:00Z",
            updated_at=session.updated_at.isoformat() if session.updated_at else "2026-09-14T00:00:00Z",
            message_count=0,
            meta=session.meta,
        )

    async def get_session(
        self,
        db: AsyncSession,
        session_id: UUID,
        tenant_id: UUID,
        workspace_id: UUID,
    ) -> ChatSession:
        stmt = select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.tenant_id == tenant_id,
            ChatSession.workspace_id == workspace_id,
        )
        res = await db.execute(stmt)
        session = res.scalar_one_or_none()
        if not session:
            raise AppException("Chat session not found.", status_code=404, error_code="SESSION_NOT_FOUND")
        return session

    async def list_sessions(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ChatSessionResponse]:
        stmt = (
            select(ChatSession, func.count(ChatMessage.id).label("msg_count"))
            .outerjoin(ChatMessage, ChatSession.id == ChatMessage.session_id)
            .where(
                ChatSession.tenant_id == tenant_id,
                ChatSession.workspace_id == workspace_id,
                ChatSession.user_id == user_id,
            )
            .group_by(ChatSession.id)
            .order_by(desc(ChatSession.updated_at))
            .limit(limit)
            .offset(offset)
        )
        res = await db.execute(stmt)
        rows = res.all()

        sessions: list[ChatSessionResponse] = []
        for session, msg_count in rows:
            sessions.append(
                ChatSessionResponse(
                    id=session.id,
                    tenant_id=session.tenant_id,
                    workspace_id=session.workspace_id,
                    user_id=session.user_id,
                    title=session.title,
                    created_at=session.created_at.isoformat() if session.created_at else "2026-09-14T00:00:00Z",
                    updated_at=session.updated_at.isoformat() if session.updated_at else "2026-09-14T00:00:00Z",
                    message_count=msg_count or 0,
                    meta=session.meta,
                )
            )
        return sessions

    async def update_title(
        self,
        db: AsyncSession,
        session_id: UUID,
        tenant_id: UUID,
        workspace_id: UUID,
        new_title: str,
    ) -> ChatSessionResponse:
        session = await self.get_session(db, session_id, tenant_id, workspace_id)
        session.title = new_title
        await db.commit()
        await db.refresh(session)
        return ChatSessionResponse(
            id=session.id,
            tenant_id=session.tenant_id,
            workspace_id=session.workspace_id,
            user_id=session.user_id,
            title=session.title,
            created_at=session.created_at.isoformat() if session.created_at else "2026-09-14T00:00:00Z",
            updated_at=session.updated_at.isoformat() if session.updated_at else "2026-09-14T00:00:00Z",
            meta=session.meta,
        )

    async def delete_session(
        self,
        db: AsyncSession,
        session_id: UUID,
        tenant_id: UUID,
        workspace_id: UUID,
    ) -> None:
        session = await self.get_session(db, session_id, tenant_id, workspace_id)
        await db.delete(session)
        await db.commit()

    async def add_message(
        self,
        db: AsyncSession,
        session_id: UUID,
        role: MessageRole,
        content: str,
        citations: list[dict[str, Any]] | None = None,
        tokens_used: int = 0,
    ) -> ChatMessage:
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            citations=citations or [],
            tokens_used=tokens_used,
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        return msg

    async def get_messages(
        self,
        db: AsyncSession,
        session_id: UUID,
        limit: int = 100,
    ) -> list[ChatMessageResponse]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )
        res = await db.execute(stmt)
        messages = res.scalars().all()
        result: list[ChatMessageResponse] = []
        for m in messages:
            citations = [CitationPayload(**c) for c in m.citations] if isinstance(m.citations, list) else []
            result.append(
                ChatMessageResponse(
                    id=m.id,
                    session_id=m.session_id,
                    role=m.role.value if hasattr(m.role, "value") else str(m.role),
                    content=m.content,
                    citations=citations,
                    tokens_used=m.tokens_used,
                    created_at=m.created_at.isoformat(),
                )
            )
        return result

    async def maybe_auto_title(self, db: AsyncSession, session: ChatSession, first_query: str) -> None:
        if session.title and session.title != "New Chat":
            return

        try:
            # Fast title generation
            messages = [
                {"role": "system", "content": "Generate a concise 3-5 word title summarizing the user query. Output ONLY the title."},
                {"role": "user", "content": first_query},
            ]
            res = await litellm_client.acompletion(messages=messages, temperature=0.3, max_tokens=20)
            choices = res.get("choices", [])
            if choices:
                title = choices[0]["message"]["content"].strip().strip('"')
                session.title = title[:100]
                await db.commit()
                logger.info("chat_session_auto_titled", session_id=str(session.id), title=title)
        except Exception as e:
            logger.debug("auto_title_failed_using_fallback", error=str(e))
            words = first_query.split()[:5]
            session.title = " ".join(words).capitalize()
            await db.commit()

    async def export_markdown(self, db: AsyncSession, session: ChatSession) -> str:
        messages = await self.get_messages(db, session.id)
        lines = [f"# Chat Export: {session.title}", f"Exported on: {session.updated_at.isoformat()}\n", "---"]
        for m in messages:
            lines.append(f"### {m.role.upper()}")
            lines.append(m.content)
            if m.citations:
                lines.append("\n**Sources Cited:**")
                for c in m.citations:
                    page_info = f", Page {c.page_number}" if c.page_number else ""
                    lines.append(f"- `[{c.source_index}]` {c.document_name}{page_info}: {c.snippet}")
            lines.append("\n---\n")
        return "\n".join(lines)

    async def create_share_link(self, session_id: UUID) -> str:
        token = f"share_{uuid.uuid4().hex}"
        redis = await get_redis_client()
        # Shared link valid for 30 days
        await redis.setex(f"shared_chat:{token}", 30 * 86400, str(session_id))
        return token


session_service = ChatSessionService()
