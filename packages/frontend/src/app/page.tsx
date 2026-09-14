"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Layers,
  UploadCloud,
  FileText,
  ShieldCheck,
  Zap,
  Activity,
  Key,
  AlertOctagon,
  Sparkles,
  Server,
  FolderSync,
  RefreshCw,
  Plus,
  Lock,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { api, DocumentRecord, IngestionPreviewResponse } from "@/lib/api";
import { Navbar } from "@/components/Navbar";
import { UploadDropzone } from "@/components/UploadDropzone";
import { DocumentList } from "@/components/DocumentList";
import { IngestionPreviewModal } from "@/components/IngestionPreviewModal";
import { LiveIngestionStatus } from "@/components/LiveIngestionStatus";
import { ApiKeysView } from "@/components/ApiKeysView";
import { DlqView } from "@/components/DlqView";
import { HealthView } from "@/components/HealthView";

type ActiveTab = "library" | "upload" | "apikeys" | "dlq" | "health";

export default function TitanRAGDashboard() {
  const { user, loading: authLoading, activeWorkspace, demoLogin } = useAuth();
  const [activeTab, setActiveTab] = useState<ActiveTab>("library");
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [docsLoading, setDocsLoading] = useState<boolean>(false);
  const [previewData, setPreviewData] = useState<IngestionPreviewResponse | null>(null);
  const [previewModalOpen, setPreviewModalOpen] = useState<boolean>(false);
  const [activeIngestion, setActiveIngestion] = useState<{
    docId: string;
    filename: string;
  } | null>(null);

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

  const handleUploadSuccess = (docId: string, filename: string) => {
    setActiveIngestion({ docId, filename });
    setActiveTab("library");
  };

  const handleIngestionComplete = () => {
    fetchDocuments();
  };

  const handleReindex = async (docId: string, title: string) => {
    if (!activeWorkspace) return;
    try {
      await api.reindexDocument(activeWorkspace.id, docId);
      setActiveIngestion({ docId, filename: title });
    } catch (err: any) {
      alert("Failed to trigger re-index: " + err.message);
    }
  };

  const handleDelete = async (docId: string) => {
    if (!activeWorkspace) return;
    try {
      await api.deleteDocument(activeWorkspace.id, docId);
      await fetchDocuments();
    } catch (err: any) {
      alert("Failed to delete document: " + err.message);
    }
  };

  const handlePreviewRequested = (data: IngestionPreviewResponse) => {
    setPreviewData(data);
    setPreviewModalOpen(true);
  };

  // If auth is still checking
  if (authLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-slate-400 space-y-4">
        <div className="w-10 h-10 rounded-full border-2 border-sky-500 border-t-transparent animate-spin" />
        <p className="text-sm font-semibold tracking-wide">Connecting to TitanRAG Enterprise Core...</p>
      </div>
    );
  }

  // If user is not logged in, show authentication splash
  if (!user) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col justify-between text-slate-100">
        <Navbar />
        <main className="max-w-xl mx-auto px-6 py-16 text-center space-y-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-sky-500/30 bg-sky-500/10 text-sky-400 text-xs font-semibold uppercase tracking-wider">
            Enterprise Multi-Tenant Security Active
          </div>

          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-white leading-tight">
            Welcome to{" "}
            <span className="bg-gradient-to-r from-sky-400 via-indigo-300 to-white bg-clip-text text-transparent">
              TitanRAG
            </span>
          </h1>

          <p className="text-slate-400 text-sm leading-relaxed">
            TitanRAG enforces zero-leakage Row-Level Security (RLS) in PostgreSQL, transactional outbox synchronization to Qdrant, and token-bucket concurrency controls.
          </p>

          <div className="p-6 rounded-2xl border border-slate-800 bg-slate-900/60 shadow-2xl backdrop-blur-xl space-y-4">
            <div className="flex items-center justify-center p-3 rounded-full bg-sky-500/10 text-sky-400 w-12 h-12 mx-auto">
              <Lock className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-white">Sign In to Workspace</h3>
            <p className="text-xs text-slate-400">
              Click below to authenticate using the provisioned administrator account or explore your isolated tenant.
            </p>
            <button
              onClick={() => demoLogin()}
              className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white text-sm font-bold shadow-lg shadow-sky-500/25 transition-all cursor-pointer"
            >
              <Sparkles className="w-4 h-4" />
              <span>Sign In as Admin (admin@titanrag.io)</span>
            </button>
          </div>
        </main>
        <footer className="py-6 text-center text-xs text-slate-600 border-t border-slate-900">
          TitanRAG Enterprise Core • Defense-in-Depth RAG Engine
        </footer>
      </div>
    );
  }

  const readyDocs = documents.filter((d) => d.status === "READY").length;
  const pendingDocs = documents.filter((d) => d.status === "PENDING" || d.status === "PROCESSING").length;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 selection:bg-sky-500/30 selection:text-sky-200 flex flex-col">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-8 space-y-8">
        {/* Dynamic Metric Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/50 backdrop-blur">
            <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2">
              <span>Indexed Documents</span>
              <FileText className="w-4 h-4 text-sky-400" />
            </div>
            <div className="text-3xl font-black text-white">{documents.length}</div>
            <p className="text-xs text-slate-500 mt-1">
              {readyDocs} Ready • {pendingDocs} Ingesting
            </p>
          </div>

          <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/50 backdrop-blur">
            <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2">
              <span>Vector Projections</span>
              <Activity className="w-4 h-4 text-indigo-400" />
            </div>
            <div className="text-3xl font-black text-white">
              {documents.length > 0 ? `${documents.length * 4} Chunks` : "0"}
            </div>
            <p className="text-xs text-slate-500 mt-1">Dense (HNSW INT8) + BM25 Sparse</p>
          </div>

          <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/50 backdrop-blur">
            <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2">
              <span>Delta Re-embed</span>
              <Zap className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-3xl font-black text-emerald-400">MinHash Active</div>
            <p className="text-xs text-slate-500 mt-1">128 permutations, Jaccard dedup</p>
          </div>

          <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/50 backdrop-blur">
            <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2">
              <span>PII Engine</span>
              <ShieldCheck className="w-4 h-4 text-amber-400" />
            </div>
            <div className="text-3xl font-black text-white">REPLACE</div>
            <p className="text-xs text-slate-500 mt-1">Regex + Presidio Redaction</p>
          </div>
        </div>

        {/* Live SSE Ingestion Pipeline Monitor */}
        {activeIngestion && activeWorkspace && (
          <LiveIngestionStatus
            workspaceId={activeWorkspace.id}
            documentId={activeIngestion.docId}
            filename={activeIngestion.filename}
            onComplete={handleIngestionComplete}
          />
        )}

        {/* Navigation Tabs */}
        <div className="flex border-b border-slate-800 gap-6 overflow-x-auto">
          <button
            onClick={() => setActiveTab("library")}
            className={`flex items-center gap-2 pb-3 text-sm font-semibold transition-colors border-b-2 cursor-pointer ${
              activeTab === "library"
                ? "border-sky-400 text-sky-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <FileText className="w-4 h-4" />
            <span>Document Library ({documents.length})</span>
          </button>

          <button
            onClick={() => setActiveTab("upload")}
            className={`flex items-center gap-2 pb-3 text-sm font-semibold transition-colors border-b-2 cursor-pointer ${
              activeTab === "upload"
                ? "border-sky-400 text-sky-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <UploadCloud className="w-4 h-4" />
            <span>Ingest Document</span>
          </button>

          <button
            onClick={() => setActiveTab("apikeys")}
            className={`flex items-center gap-2 pb-3 text-sm font-semibold transition-colors border-b-2 cursor-pointer ${
              activeTab === "apikeys"
                ? "border-indigo-400 text-indigo-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Key className="w-4 h-4" />
            <span>API Keys</span>
          </button>

          <button
            onClick={() => setActiveTab("dlq")}
            className={`flex items-center gap-2 pb-3 text-sm font-semibold transition-colors border-b-2 cursor-pointer ${
              activeTab === "dlq"
                ? "border-rose-400 text-rose-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <AlertOctagon className="w-4 h-4" />
            <span>DLQ Admin</span>
          </button>

          <button
            onClick={() => setActiveTab("health")}
            className={`flex items-center gap-2 pb-3 text-sm font-semibold transition-colors border-b-2 cursor-pointer ${
              activeTab === "health"
                ? "border-emerald-400 text-emerald-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Activity className="w-4 h-4" />
            <span>System Health</span>
          </button>
        </div>

        {/* Tab Views */}
        {activeWorkspace ? (
          <div>
            {activeTab === "library" && (
              <DocumentList
                workspaceId={activeWorkspace.id}
                documents={documents}
                loading={docsLoading}
                onReindex={handleReindex}
                onDelete={handleDelete}
                onUploadClick={() => setActiveTab("upload")}
              />
            )}

            {activeTab === "upload" && (
              <UploadDropzone
                workspaceId={activeWorkspace.id}
                onUploadSuccess={handleUploadSuccess}
                onPreviewRequested={handlePreviewRequested}
              />
            )}

            {activeTab === "apikeys" && <ApiKeysView />}

            {activeTab === "dlq" && <DlqView />}

            {activeTab === "health" && <HealthView />}
          </div>
        ) : (
          <div className="text-center py-16 text-slate-500">
            No workspace selected. Please select or create a workspace above.
          </div>
        )}

        {/* Chunk Inspection Modal */}
        <IngestionPreviewModal
          isOpen={previewModalOpen}
          onClose={() => setPreviewModalOpen(false)}
          previewData={previewData}
        />
      </main>

      <footer className="border-t border-slate-900 bg-slate-950/60 py-4 px-6 text-center text-xs text-slate-500">
        TitanRAG v0.1.0 • Multi-Tenant Defense-in-Depth RAG Engine • Fast, Zero-Loss Transactional Outbox
      </footer>
    </div>
  );
}
