"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/lib/auth";
import { api, DocumentRecord, IngestionPreviewResponse } from "@/lib/api";
import { UploadDropzone } from "@/components/UploadDropzone";
import { DocumentList } from "@/components/DocumentList";
import { IngestionPreviewModal } from "@/components/IngestionPreviewModal";
import { LiveIngestionStatus } from "@/components/LiveIngestionStatus";

export default function DocumentsPage() {
  const { activeWorkspace } = useAuth();
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [previewData, setPreviewData] = useState<IngestionPreviewResponse | null>(null);
  const [previewModalOpen, setPreviewModalOpen] = useState(false);
  const [activeIngestion, setActiveIngestion] = useState<{ docId: string; filename: string } | null>(null);

  const fetchDocuments = useCallback(async () => {
    if (!activeWorkspace) return;
    setDocsLoading(true);
    try {
      const res = await api.listDocuments(activeWorkspace.id);
      setDocuments(res.items);
    } catch (err: any) {
      console.warn("Could not fetch documents:", err.message);
    } finally {
      setDocsLoading(false);
    }
  }, [activeWorkspace]);

  useEffect(() => {
    if (activeWorkspace) {
      fetchDocuments();
    }
  }, [activeWorkspace, fetchDocuments]);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {activeIngestion && (
        <LiveIngestionStatus
          workspaceId={activeWorkspace?.id || ""}
          documentId={activeIngestion.docId}
          filename={activeIngestion.filename}
          onComplete={() => {
            setActiveIngestion(null);
            fetchDocuments();
          }}
        />
      )}

      <UploadDropzone
        workspaceId={activeWorkspace?.id || ""}
        onUploadSuccess={(docId, filename) => {
          setActiveIngestion({ docId, filename });
        }}
        onPreviewRequested={(data) => {
          setPreviewData(data);
          setPreviewModalOpen(true);
        }}
      />

      <DocumentList
        workspaceId={activeWorkspace?.id || ""}
        documents={documents}
        loading={docsLoading}
        onReindex={async (docId, title) => {
          if (!activeWorkspace) return;
          await api.reindexDocument(activeWorkspace.id, docId);
          setActiveIngestion({ docId, filename: title });
        }}
        onDelete={async (docId) => {
          if (!activeWorkspace) return;
          await api.deleteDocument(activeWorkspace.id, docId);
          await fetchDocuments();
        }}
        onUploadClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
      />

      {previewData && (
        <IngestionPreviewModal
          isOpen={previewModalOpen}
          onClose={() => setPreviewModalOpen(false)}
          previewData={previewData}
        />
      )}
    </div>
  );
}
