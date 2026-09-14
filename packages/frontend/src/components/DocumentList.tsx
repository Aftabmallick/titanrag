"use client";

import React, { useState } from "react";
import {
  FileText,
  RefreshCw,
  Trash2,
  Share2,
  Eye,
  Search,
  Folder,
  Tag,
  CheckCircle2,
  Clock,
  AlertTriangle,
  FileCode,
  FileSpreadsheet,
  Presentation,
  Sparkles,
  Loader2,
} from "lucide-react";
import { DocumentRecord } from "@/lib/api";

interface DocumentListProps {
  workspaceId: string;
  documents: DocumentRecord[];
  loading?: boolean;
  onReindex: (docId: string, title: string) => Promise<void>;
  onDelete: (docId: string) => Promise<void>;
  onUploadClick: () => void;
}

function getFileIcon(filename: string) {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".pdf")) return <FileText className="w-4 h-4 text-rose-400" />;
  if (lower.endsWith(".csv") || lower.endsWith(".tsv"))
    return <FileSpreadsheet className="w-4 h-4 text-emerald-400" />;
  if (lower.endsWith(".pptx") || lower.endsWith(".ppt"))
    return <Presentation className="w-4 h-4 text-amber-400" />;
  if (lower.endsWith(".md") || lower.endsWith(".txt"))
    return <FileCode className="w-4 h-4 text-sky-400" />;
  return <FileText className="w-4 h-4 text-slate-400" />;
}

function formatBytes(bytes: number) {
  if (!bytes) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

export function DocumentList({
  workspaceId,
  documents,
  loading = false,
  onReindex,
  onDelete,
  onUploadClick,
}: DocumentListProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [folderFilter, setFolderFilter] = useState("ALL");
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);

  const folders = Array.from(new Set(documents.map((d) => d.folder).filter(Boolean)));

  const filteredDocs = documents.filter((d) => {
    const matchesSearch = d.title.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesFolder = folderFilter === "ALL" || d.folder === folderFilter;
    return matchesSearch && matchesFolder;
  });

  const handleReindexClick = async (doc: DocumentRecord) => {
    setActionLoadingId(`reindex-${doc.id}`);
    try {
      await onReindex(doc.id, doc.title);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleDeleteClick = async (doc: DocumentRecord) => {
    if (!confirm(`Are you sure you want to delete "${doc.title}"? This will also remove all its vector projections.`)) {
      return;
    }
    setActionLoadingId(`delete-${doc.id}`);
    try {
      await onDelete(doc.id);
    } finally {
      setActionLoadingId(null);
    }
  };

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-xl shadow-2xl space-y-4">
      {/* Table Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <FileText className="w-5 h-5 text-sky-400" />
            Workspace Documents
          </h2>
          <p className="text-sm text-slate-400">
            {documents.length} ingested documents stored in PostgreSQL & indexed in Qdrant
          </p>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search documents..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950/80 pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500 w-48"
            />
          </div>

          <select
            value={folderFilter}
            onChange={(e) => setFolderFilter(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-950/80 px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500 cursor-pointer"
          >
            <option value="ALL">All Folders</option>
            {folders.map((f) => (
              <option key={f} value={f!}>
                📁 {f}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Documents Table */}
      <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/50">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-slate-900/80 text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800">
            <tr>
              <th className="py-3 px-4 font-semibold">Document</th>
              <th className="py-3 px-4 font-semibold">Folder / Namespace</th>
              <th className="py-3 px-4 font-semibold">Status</th>
              <th className="py-3 px-4 font-semibold">Type</th>
              <th className="py-3 px-4 font-semibold">Size</th>
              <th className="py-3 px-4 font-semibold">Indexed At</th>
              <th className="py-3 px-4 font-semibold text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {loading ? (
              <tr>
                <td colSpan={7} className="py-12 text-center text-slate-400">
                  <div className="flex items-center justify-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin text-sky-400" />
                    <span>Loading documents from backend...</span>
                  </div>
                </td>
              </tr>
            ) : filteredDocs.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-12 text-center text-slate-400">
                  <div className="max-w-sm mx-auto space-y-3">
                    <div className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center mx-auto text-slate-500">
                      <FileText className="w-5 h-5" />
                    </div>
                    <p className="text-sm font-semibold text-slate-300">No documents found in this workspace</p>
                    <p className="text-xs text-slate-500">
                      Upload your first PDF, DOCX, presentation, or table to launch the ingestion pipeline.
                    </p>
                    <button
                      onClick={onUploadClick}
                      className="px-4 py-1.5 rounded-lg bg-sky-500/10 hover:bg-sky-500/20 text-sky-300 text-xs font-semibold border border-sky-500/30 transition-colors"
                    >
                      Ingest New Document
                    </button>
                  </div>
                </td>
              </tr>
            ) : (
              filteredDocs.map((doc) => {
                const isReindexing = actionLoadingId === `reindex-${doc.id}`;
                const isDeleting = actionLoadingId === `delete-${doc.id}`;

                return (
                  <tr key={doc.id} className="hover:bg-slate-900/40 transition-colors">
                    <td className="py-3.5 px-4 font-medium text-white flex items-center gap-2.5">
                      {getFileIcon(doc.title)}
                      <div className="truncate max-w-xs">
                        <div className="truncate text-slate-100 font-semibold">{doc.title}</div>
                        <div className="text-[10px] text-slate-500 font-mono truncate">{doc.id}</div>
                      </div>
                    </td>

                    <td className="py-3.5 px-4 text-slate-300">
                      {doc.folder ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-800 text-slate-300 font-mono text-[11px]">
                          📁 {doc.folder}
                        </span>
                      ) : (
                        <span className="text-slate-600 font-mono">—</span>
                      )}
                    </td>

                    <td className="py-3.5 px-4">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold font-mono tracking-wider ${
                          doc.status === "READY"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : doc.status === "PENDING" || doc.status === "PROCESSING"
                            ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                            : doc.status === "FAILED"
                            ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                            : "bg-slate-800 text-slate-300"
                        }`}
                      >
                        {doc.status === "READY" && <CheckCircle2 className="w-3 h-3" />}
                        {doc.status === "PENDING" && <Clock className="w-3 h-3 animate-spin" />}
                        {doc.status}
                      </span>
                    </td>

                    <td className="py-3.5 px-4 capitalize text-slate-400 font-mono text-[11px]">
                      {doc.doc_type}
                    </td>

                    <td className="py-3.5 px-4 text-slate-400 font-mono text-[11px]">
                      {formatBytes(doc.file_size_bytes)}
                    </td>

                    <td className="py-3.5 px-4 text-slate-400 font-mono text-[11px]">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </td>

                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => handleReindexClick(doc)}
                          disabled={isReindexing || isDeleting}
                          title="Re-index document (MinHash delta re-embed)"
                          className="p-1.5 rounded-lg border border-slate-800 hover:border-sky-500/40 hover:bg-sky-500/10 text-slate-400 hover:text-sky-300 transition-colors disabled:opacity-50"
                        >
                          <RefreshCw className={`w-3.5 h-3.5 ${isReindexing ? "animate-spin" : ""}`} />
                        </button>

                        <button
                          onClick={() => handleDeleteClick(doc)}
                          disabled={isDeleting || isReindexing}
                          title="Delete document and purge vectors"
                          className="p-1.5 rounded-lg border border-slate-800 hover:border-rose-500/40 hover:bg-rose-500/10 text-slate-400 hover:text-rose-400 transition-colors disabled:opacity-50"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
