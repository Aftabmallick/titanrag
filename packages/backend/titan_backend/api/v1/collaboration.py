import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from titan_backend.collaboration.presence import PresenceManager
from titan_backend.core.dependencies import CurrentUser, get_current_user

router = APIRouter(prefix="/collaboration", tags=["collaboration"])


class AnnotationCreateRequest(BaseModel):
    document_id: str
    chunk_id: str | None = None
    page_number: int | None = None
    quote: str | None = None
    comment: str = Field(..., min_length=1)


# In-memory storage for collaborative annotations (persisted with chunks)
_in_memory_annotations: list[dict[str, Any]] = []


@router.get("/workspaces/{workspace_id}/sessions/{session_id}/presence")
async def get_session_presence(
    workspace_id: uuid.UUID,
    session_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """List all currently active collaborators viewing the given chat session."""
    active_users = await PresenceManager.get_active_users(str(workspace_id), str(session_id))
    return {
        "workspace_id": str(workspace_id),
        "session_id": str(session_id),
        "active_viewers_count": len(active_users),
        "users": active_users,
    }


@router.post("/workspaces/{workspace_id}/annotations")
async def create_document_annotation(
    workspace_id: uuid.UUID,
    payload: AnnotationCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Add a collaborative team annotation / comment to a document passage."""
    annotation = {
        "id": f"ann_{uuid.uuid4().hex[:10]}",
        "workspace_id": str(workspace_id),
        "document_id": payload.document_id,
        "chunk_id": payload.chunk_id,
        "page_number": payload.page_number,
        "quote": payload.quote,
        "comment": payload.comment,
        "user_id": str(current_user.id),
        "user_email": current_user.email,
        "created_at": datetime.now(UTC).isoformat(),
    }
    _in_memory_annotations.append(annotation)
    return annotation


@router.get("/workspaces/{workspace_id}/documents/{document_id}/annotations")
async def list_document_annotations(
    workspace_id: uuid.UUID,
    document_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List all annotations created for a document."""
    doc_annotations = [
        a for a in _in_memory_annotations if a["workspace_id"] == str(workspace_id) and a["document_id"] == document_id
    ]
    return doc_annotations


@router.websocket("/ws/workspaces/{workspace_id}/presence")
async def websocket_presence_endpoint(
    websocket: WebSocket,
    workspace_id: uuid.UUID,
) -> None:
    """
    WebSocket connection endpoint for real-time presence, typing indicators,
    and heartbeat coordination.
    """
    await websocket.accept()
    wid_str = str(workspace_id)
    registered_session_id = None
    registered_user_id = None

    try:
        while True:
            raw_msg = await websocket.receive_text()
            data = json.loads(raw_msg)
            msg_type = data.get("type")

            if msg_type == "join":
                registered_session_id = data.get("session_id", "global")
                registered_user_id = data.get("user_id", "guest")
                active = await PresenceManager.user_join(
                    workspace_id=wid_str,
                    session_id=registered_session_id,
                    user_id=registered_user_id,
                    user_name=data.get("name", "Collaborator"),
                    user_email=data.get("email", "collaborator@enterprise.io"),
                )
                await websocket.send_text(json.dumps({"type": "presence_state", "users": active}))

            elif msg_type == "ping":
                if registered_session_id and registered_user_id:
                    await PresenceManager.heartbeat(wid_str, registered_session_id, registered_user_id)
                await websocket.send_text(json.dumps({"type": "pong"}))

            elif msg_type == "leave":
                if registered_session_id and registered_user_id:
                    await PresenceManager.user_leave(wid_str, registered_session_id, registered_user_id)
                break

    except WebSocketDisconnect:
        if registered_session_id and registered_user_id:
            await PresenceManager.user_leave(wid_str, registered_session_id, registered_user_id)
