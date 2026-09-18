import email
import hashlib
import uuid
from email import policy
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from titan_backend.clients.s3_client import get_minio_client
from titan_backend.db.models.documents import Document, DocumentStatus, DocumentVersion

logger = structlog.get_logger("titanrag.integrations.email")


class InboundEmailParser:
    """
    Parses inbound emails from webhook payloads (SendGrid, Mailgun, Postmark, or raw MIME).
    Extracts message text, and uploads file attachments into MinIO and queues ingestion.
    """

    @classmethod
    async def process_raw_email(
        cls,
        session: AsyncSession,
        raw_email_bytes: bytes,
        tenant_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> dict[str, Any]:
        msg = email.message_from_bytes(raw_email_bytes, policy=policy.default)
        sender = msg.get("from", "")
        subject = msg.get("subject", "No Subject")

        # Extract text content
        body_text = ""
        body_part = msg.get_body(preferencelist=("plain", "html"))
        if body_part:
            body_text = body_part.get_content()

        attachments_processed: list[str] = []
        minio_client = get_minio_client()

        import io

        # Extract attachments
        for part in msg.iter_attachments():
            fn = part.get_filename() or f"attachment_{uuid.uuid4().hex[:8]}.bin"
            content_type = part.get_content_type()
            payload = part.get_payload(decode=True)
            if not isinstance(payload, bytes) or not payload:
                continue

            doc_id = uuid.uuid4()
            s3_key = f"{tenant_id}/{workspace_id}/{doc_id}/{fn}"
            content_hash = hashlib.sha256(payload).hexdigest()

            minio_client.put_object(
                bucket_name="titanrag-documents",
                object_name=s3_key,
                data=io.BytesIO(payload),
                length=len(payload),
                content_type=content_type,
            )

            new_doc = Document(
                id=doc_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                title=f"[Email Attachment] {fn}",
                mime_type=content_type,
                file_size_bytes=len(payload),
                status=DocumentStatus.PROCESSING,
                storage_path=s3_key,
                content_hash=content_hash,
                meta={
                    "email_sender": sender,
                    "email_subject": subject,
                    "source": "email_inbound",
                },
            )
            session.add(new_doc)
            doc_ver = DocumentVersion(
                document_id=new_doc.id,
                version_number=1,
                storage_path=s3_key,
                content_hash=content_hash,
            )
            session.add(doc_ver)
            attachments_processed.append(fn)

        await session.commit()

        return {
            "sender": sender,
            "subject": subject,
            "body_length": len(body_text),
            "attachments_count": len(attachments_processed),
            "attachments": attachments_processed,
        }
