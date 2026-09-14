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
} from "lucide-react";

export interface DocumentItem {
  id: string;
  title: string;
  folder: string | null;
  doc_type: string;
  status: string;
  tags: string[];
  file_size_bytes: number;
  created_at: string;
  is_stale?: boolean;
}

interface DocumentListProps {
  workspaceId: string;
  documents: DocumentItem[];
  onReindex: (docId: string, title: string) => void;
  onPreview: (doc: DocumentItem) => void;
  onDelete: (docId: string) => void;
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
  onReindex,
  onPreview,
  onDelete,
}: DocumentListProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [folderFilter, setFolderFilter] = useState("ALL");

  const folders = Array.from(new Set(documents.map((d) => d.folder).filter(Boolean)));

  const filteredDocs = documents.filter((d) => {
    const matchesSearch = d.title.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesFolder = folderFilter === "ALL" || d.folder === folderFilter;
    return matchesSearch && matchesFolder;
  });

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
            {documents.length} ingested documents actively indexed in Qdrant & PostgreSQL
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
            className="rounded-lg border border-slate-700 bg-slate-950/80 px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
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

      {/* Document Table */}
      <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/50">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-900/80 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
            <tr>
              <th className="px-4 py-3">Document</th>
              <th className="px-4 py-3">Folder</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Size</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {filteredDocs.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  No matching documents found. Upload documents using the dropzone above.
                </td>
              </tr>
            ) : (
              filteredDocs.map((doc) => (
                <tr
                  key={doc.id}
                  className="hover:bg-slate-900/40 transition-colors group"
                >
                  <td className="px-4 py-3.5">
                    <div className="flex items-center gap-2.5">
                      <div className="p-2 rounded-lg bg-slate-800/80 shrink-0">
                        {getFileIcon(doc.title)}
                      </div>
                      <div>
                        <span className="font-semibold text-slate-200 block">
                          {doc.title}
                        </span>
                        {doc.tags && doc.tags.length > 0 && (
                          <div className="flex items-center gap-1 mt-1">
                            {doc.tags.map((t) => (
                              <span
                                key={t}
                                className="px-1.5 py-0.2 rounded bg-slate-800 text-[10px] text-slate-400"
                              >
                                #{t}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </td>

                  <td className="px-4 py-3.5 text-slate-400">
                    {doc.folder ? (
                      <span className="inline-flex items-center gap-1 rounded bg-slate-800/60 px-2 py-0.5 text-[11px] text-slate-300">
                        <Folder className="w-3 h-3 text-sky-400" />
                        {doc.folder}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>

                  <td className="px-4 py-3.5">
                    <span className="rounded bg-slate-800 px-2 py-0.5 text-[11px] font-mono text-slate-300">
                      {doc.doc_type}
                    </span>
                  </td>

                  <td className="px-4 py-3.5">
                    {doc.is_stale ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-purple-500/10 px-2 py-0.5 text-[11px] font-medium text-purple-400 border border-purple-500/20">
                        <Clock className="w-3 h-3" /> Stale (Decayed)
                      </span>
                    ) : doc.status === "READY" ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-400 border border-emerald-500/20">
                        <CheckCircle2 className="w-3 h-3" /> Ready
                      </span>
                    ) : doc.status === "FAILED" ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/10 px-2 py-0.5 text-[11px] font-medium text-rose-400 border border-rose-500/20">
                        <AlertTriangle className="w-3 h-3" /> Failed
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full bg-sky-500/10 px-2 py-0.5 text-[11px] font-medium text-sky-400 border border-sky-500/20">
                        <RefreshCw className="w-3 h-3 animate-spin" /> Ingestion
                      </span>
                    )}
                  </td>

                  <td className="px-4 py-3.5 text-slate-400 font-mono text-[11px]">
                    {formatBytes(doc.file_size_bytes)}
                  </td>

                  <td className="px-4 py-3.5 text-right">
                    <div className="flex items-center justify-end gap-1.5 opacity-80 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => onPreview(doc)}
                        title="Preview Chunks & Prefixes"
                        className="p-1.5 rounded-lg bg-slate-800/80 text-slate-400 hover:text-sky-400 hover:bg-slate-800 transition-colors"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => onReindex(doc.id, doc.title)}
                        title="Re-index Document"
                        className="p-1.5 rounded-lg bg-slate-800/80 text-slate-400 hover:text-amber-400 hover:bg-slate-800 transition-colors"
                      >
                        <RefreshCw className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => onDelete(doc.id)}
                        title="Delete Document & Purge Vectors"
                        className="p-1.5 rounded-lg bg-slate-800/80 text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
