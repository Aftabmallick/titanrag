"use client";

import React, { useState } from "react";
import {
  Layers,
  UploadCloud,
  FileText,
  ShieldCheck,
  Zap,
  Activity,
  Sparkles,
  Server,
  FolderSync,
} from "lucide-react";
import { UploadDropzone } from "@/components/UploadDropzone";
import { LiveIngestionStatus } from "@/components/LiveIngestionStatus";
import { DocumentList, DocumentItem } from "@/components/DocumentList";
import { IngestionPreviewModal } from "@/components/IngestionPreviewModal";

const INITIAL_DOCS: DocumentItem[] = [
  {
    id: "doc-1",
    title: "titanrag_architecture_spec_v2.pdf",
    folder: "Architecture",
    doc_type: "technical",
    status: "READY",
    tags: ["core", "v2", "hnsw"],
    file_size_bytes: 2457600,
    created_at: "2026-09-14T09:30:00Z",
  },
  {
    id: "doc-2",
    title: "financial_metrics_q2_2026.csv",
    folder: "Finance",
    doc_type: "financial",
    status: "READY",
    tags: ["q2", "earnings", "metrics"],
    file_size_bytes: 419430,
    created_at: "2026-09-14T10:15:00Z",
  },
  {
    id: "doc-3",
    title: "board_strategy_deck.pptx",
    folder: "Executive",
    doc_type: "presentation",
    status: "READY",
    tags: ["confidential", "strategy"],
    file_size_bytes: 5242880,
    created_at: "2026-09-14T11:45:00Z",
  },
  {
    id: "doc-4",
    title: "security_and_compliance_policy.md",
    folder: "Security",
    doc_type: "contract",
    status: "STALE",
    tags: ["soc2", "gdpr", "pii"],
    file_size_bytes: 184320,
    created_at: "2026-01-10T12:00:00Z",
    is_stale: true,
  },
];

export default function DocumentManagementPage() {
  const [documents, setDocuments] = useState<DocumentItem[]>(INITIAL_DOCS);
  const [activeTab, setActiveTab] = useState<"library" | "upload">("library");
  const [activeIngestion, setActiveIngestion] = useState<{
    docId: string;
    filename: string;
  } | null>(null);
  const [previewDoc, setPreviewDoc] = useState<DocumentItem | null>(null);

  const workspaceId = "00000000-0000-0000-0000-000000000001";

  const handleUploadSuccess = (docId: string, filename: string) => {
    setActiveIngestion({ docId, filename });
    setActiveTab("library");
  };

  const handleIngestionComplete = () => {
    if (!activeIngestion) return;
    const newDoc: DocumentItem = {
      id: activeIngestion.docId,
      title: activeIngestion.filename,
      folder: "General",
      doc_type: "generic",
      status: "READY",
      tags: ["recent", "ingested"],
      file_size_bytes: 1048576,
      created_at: new Date().toISOString(),
    };
    setDocuments((prev) => [newDoc, ...prev]);
  };

  const handleReindex = (docId: string, title: string) => {
    setActiveIngestion({ docId, filename: title });
  };

  const handleDelete = (docId: string) => {
    setDocuments((prev) => prev.filter((d) => d.id !== docId));
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 selection:bg-sky-500/30 selection:text-sky-200">
      {/* Top Navbar */}
      <header className="sticky top-0 z-40 border-b border-slate-800 bg-slate-950/80 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 text-white shadow-lg shadow-sky-500/20">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <span className="font-extrabold text-base tracking-tight text-white flex items-center gap-2">
                TitanRAG
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full border border-sky-500/30 bg-sky-500/10 text-sky-400">
                  Phase 3 Enterprise
                </span>
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900/60 text-xs text-slate-300">
              <FolderSync className="w-3.5 h-3.5 text-sky-400" />
              <span>Workspace: <strong>Core Engineering</strong></span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900/60 text-xs">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-slate-300">Outbox Relay: <strong>Active</strong></span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        {/* Metric Cards Row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/50 backdrop-blur">
            <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2">
              <span>Indexed Documents</span>
              <FileText className="w-4 h-4 text-sky-400" />
            </div>
            <div className="text-3xl font-black text-white">{documents.length}</div>
            <p className="text-xs text-slate-500 mt-1">Stored in Postgres & MinIO</p>
          </div>

          <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/50 backdrop-blur">
            <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2">
              <span>Vector Projections</span>
              <Activity className="w-4 h-4 text-indigo-400" />
            </div>
            <div className="text-3xl font-black text-white">1,480</div>
            <p className="text-xs text-slate-500 mt-1">Dense (HNSW INT8) + BM25 Sparse</p>
          </div>

          <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/50 backdrop-blur">
            <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2">
              <span>Delta Re-embed Savings</span>
              <Zap className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-3xl font-black text-emerald-400">92.4%</div>
            <p className="text-xs text-slate-500 mt-1">Via 128-perm MinHash signatures</p>
          </div>

          <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/50 backdrop-blur">
            <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2">
              <span>PII Engine</span>
              <ShieldCheck className="w-4 h-4 text-amber-400" />
            </div>
            <div className="text-3xl font-black text-white">REPLACE</div>
            <p className="text-xs text-slate-500 mt-1">Active Presidio / Regex protection</p>
          </div>
        </div>

        {/* Live SSE Ingestion Pipeline Monitor */}
        {activeIngestion && (
          <LiveIngestionStatus
            workspaceId={workspaceId}
            documentId={activeIngestion.docId}
            filename={activeIngestion.filename}
            onComplete={handleIngestionComplete}
          />
        )}

        {/* Navigation Tabs */}
        <div className="flex border-b border-slate-800 gap-6">
          <button
            onClick={() => setActiveTab("library")}
            className={`flex items-center gap-2 pb-3 text-sm font-semibold transition-colors border-b-2 ${
              activeTab === "library"
                ? "border-sky-400 text-sky-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <FileText className="w-4 h-4" />
            Document Library
          </button>

          <button
            onClick={() => setActiveTab("upload")}
            className={`flex items-center gap-2 pb-3 text-sm font-semibold transition-colors border-b-2 ${
              activeTab === "upload"
                ? "border-sky-400 text-sky-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <UploadCloud className="w-4 h-4" />
            Ingest Documents
          </button>
        </div>

        {/* Tab Views */}
        {activeTab === "upload" ? (
          <UploadDropzone
            workspaceId={workspaceId}
            onUploadSuccess={handleUploadSuccess}
          />
        ) : (
          <DocumentList
            workspaceId={workspaceId}
            documents={documents}
            onReindex={handleReindex}
            onPreview={(doc) => setPreviewDoc(doc)}
            onDelete={handleDelete}
          />
        )}

        {/* Chunk Inspection Modal */}
        <IngestionPreviewModal
          isOpen={previewDoc !== null}
          onClose={() => setPreviewDoc(null)}
          documentTitle={previewDoc?.title || "Document Preview"}
        />
      </main>
    </div>
  );
}
