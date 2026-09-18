import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.clients.s3_client import get_minio_client
from titan_backend.core.dependencies import CurrentUser, get_current_user, get_db
from titan_backend.db.models.documents import Document
from titan_backend.db.models.media import MediaTranscription

router = APIRouter(prefix="/workspaces/{workspace_id}/documents/{document_id}/media", tags=["media"])


@router.get("/transcript")
async def get_document_transcript(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full transcript and timecode segments for an audio or video document."""
    stmt = select(MediaTranscription).where(
        MediaTranscription.document_id == document_id,
        MediaTranscription.workspace_id == workspace_id,
        MediaTranscription.tenant_id == current_user.tenant_id,
    )
    res = await db.execute(stmt)
    trans = res.scalar_one_or_none()
    if not trans:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media transcription not found for this document",
        )

    return {
        "id": str(trans.id),
        "document_id": str(trans.document_id),
        "status": trans.status.value,
        "media_type": trans.media_type,
        "duration_seconds": trans.duration_seconds,
        "language": trans.language,
        "speaker_count": trans.speaker_count,
        "segments": trans.segments,
        "full_transcript": trans.full_transcript,
    }


@router.get("/playback-url")
async def get_media_playback_url(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a presigned streaming playback URL for the media player."""
    stmt = select(Document).where(
        Document.id == document_id,
        Document.workspace_id == workspace_id,
        Document.tenant_id == current_user.tenant_id,
    )
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    minio_client = get_minio_client()
    try:
        from datetime import timedelta
        url = minio_client.presigned_get_object(
            bucket_name="titanrag-documents",
            object_name=doc.storage_path,
            expires=timedelta(hours=2),
        )
        return {
            "document_id": str(doc.id),
            "media_url": url,
            "filename": doc.title,
            "mime_type": doc.mime_type,
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
