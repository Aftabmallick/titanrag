"use client";

import React, { useState } from "react";
import {
  FileText,
  RefreshCw,
  Trash2,
  Share2,
  History,
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
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ExternalLink,
} from "lucide-react";
import { DocumentRecord } from "@/lib/api";
import { FolderTree } from "./documents/FolderTree";
import { BulkActionToolbar } from "./documents/BulkActionToolbar";
import { VersionHistoryModal } from "./documents/VersionHistoryModal";
import { ShareDocumentModal } from "./documents/ShareDocumentModal";

interface DocumentListProps {
  workspaceId: string;
  documents: DocumentRecord[];
  loading?: boolean;
  onReindex: (docId: string, title: string) => Promise<void>;
  onDelete: (docId: string) => Promise<void>;
  onUploadClick: () => void;
}

type SortField = "title" | "file_size_bytes" | "created_at" | "status";
type SortOrder = "asc" | "desc";

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
  const [selectedDocIds, setSelectedDocIds] = useState<Set<string>>(new Set());
  const [showFolderSidebar, setShowFolderSidebar] = useState(true);

  // Sorting
  const [sortField, setSortField] = useState<SortField>("created_at");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");

  // Modals
  const [activeHistoryDoc, setActiveHistoryDoc] = useState<DocumentRecord | null>(null);
  const [activeShareDoc, setActiveShareDoc] = useState<DocumentRecord | null>(null);

  const existingFolders = Array.from(new Set(documents.map((d) => d.folder).filter(Boolean))) as string[];

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortOrder("asc");
    }
  };

  const filteredDocs = documents
    .filter((d) => {
      const matchesSearch = d.title.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesFolder = folderFilter === "ALL" || d.folder === folderFilter;
      return matchesSearch && matchesFolder;
    })
    .sort((a, b) => {
      let comparison = 0;
      if (sortField === "title") {
        comparison = a.title.localeCompare(b.title);
      } else if (sortField === "file_size_bytes") {
        comparison = a.file_size_bytes - b.file_size_bytes;
      } else if (sortField === "created_at") {
        comparison = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      } else if (sortField === "status") {
        comparison = a.status.localeCompare(b.status);
      }
      return sortOrder === "asc" ? comparison : -comparison;
    });

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedDocIds(new Set(filteredDocs.map((d) => d.id)));
    } else {
      setSelectedDocIds(new Set());
    }
  };

  const handleToggleSelect = (id: string) => {
    setSelectedDocIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleBulkReindex = async () => {
    for (const id of Array.from(selectedDocIds)) {
      const doc = documents.find((d) => d.id === id);
      if (doc) await onReindex(doc.id, doc.title);
    }
    setSelectedDocIds(new Set());
  };

  const handleBulkDelete = async () => {
    for (const id of Array.from(selectedDocIds)) {
      await onDelete(id);
    }
    setSelectedDocIds(new Set());
  };

  const handleBulkMoveFolder = async (targetFolder: string) => {
    selectedDocIds.forEach((id) => {
      const d = documents.find((doc) => doc.id === id);
      if (d) d.folder = targetFolder;
    });
    setSelectedDocIds(new Set());
  };

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

  const renderSortIndicator = (field: SortField) => {
    if (sortField !== field) {
      return <ArrowUpDown className="w-3 h-3 text-slate-600 inline ml-1 opacity-60" />;
    }
    return sortOrder === "asc" ? (
      <ArrowUp className="w-3 h-3 text-sky-400 inline ml-1" />
    ) : (
      <ArrowDown className="w-3 h-3 text-sky-400 inline ml-1" />
    );
  };

  const allSelected = filteredDocs.length > 0 && selectedDocIds.size === filteredDocs.length;
  const someSelected = selectedDocIds.size > 0 && !allSelected;

  return (
    <div className="space-y-4">
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

          {/* Filters & Actions */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowFolderSidebar((prev) => !prev)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-semibold transition-colors ${
                showFolderSidebar
                  ? "bg-sky-500/10 text-sky-400 border-sky-500/30"
                  : "bg-slate-950/80 text-slate-400 border-slate-700 hover:text-white"
              }`}
            >
              <Folder className="w-3.5 h-3.5" />
              <span>Folders</span>
            </button>

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
          </div>
        </div>

        {/* Main Content: FolderTree + Table */}
        <div className="flex flex-col lg:flex-row gap-4 items-start">
          {showFolderSidebar && (
            <FolderTree
              documents={documents}
              activeFolder={folderFilter}
              onSelectFolder={setFolderFilter}
              onCreateFolder={(newF) => setFolderFilter(newF)}
            />
          )}

          {/* Documents Table */}
          <div className="flex-1 w-full overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/50">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-900/80 text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="py-3 px-3 w-8">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      ref={(el) => {
                        if (el) el.indeterminate = someSelected;
                      }}
                      onChange={(e) => handleSelectAll(e.target.checked)}
                      className="rounded border-slate-700 bg-slate-800 text-sky-500 focus:ring-0 cursor-pointer"
                      title="Select all"
                    />
                  </th>
                  <th
                    className="py-3 px-4 font-semibold cursor-pointer select-none hover:text-slate-200"
                    onClick={() => handleSort("title")}
                  >
                    <span>Document</span>
                    {renderSortIndicator("title")}
                  </th>
                  <th className="py-3 px-4 font-semibold">Folder</th>
                  <th className="py-3 px-4 font-semibold">Tags</th>
                  <th className="py-3 px-4 font-semibold">Source</th>
                  <th
                    className="py-3 px-4 font-semibold cursor-pointer select-none hover:text-slate-200"
                    onClick={() => handleSort("status")}
                  >
                    <span>Status</span>
                    {renderSortIndicator("status")}
                  </th>
                  <th className="py-3 px-4 font-semibold">Type</th>
                  <th
                    className="py-3 px-4 font-semibold cursor-pointer select-none hover:text-slate-200"
                    onClick={() => handleSort("file_size_bytes")}
                  >
                    <span>Size</span>
                    {renderSortIndicator("file_size_bytes")}
                  </th>
                  <th
                    className="py-3 px-4 font-semibold cursor-pointer select-none hover:text-slate-200"
                    onClick={() => handleSort("created_at")}
                  >
                    <span>Indexed</span>
                    {renderSortIndicator("created_at")}
                  </th>
                  <th className="py-3 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {loading ? (
                  <tr>
                    <td colSpan={10} className="py-12 text-center text-slate-400">
                      <div className="flex items-center justify-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin text-sky-400" />
                        <span>Loading documents from backend...</span>
                      </div>
                    </td>
                  </tr>
                ) : filteredDocs.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="py-12 text-center text-slate-400">
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
                    const isChecked = selectedDocIds.has(doc.id);

                    return (
                      <tr
                        key={doc.id}
                        className={`transition-colors ${
                          isChecked ? "bg-sky-500/5 hover:bg-sky-500/10" : "hover:bg-slate-900/40"
                        }`}
                      >
                        <td className="py-3.5 px-3">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => handleToggleSelect(doc.id)}
                            className="rounded border-slate-700 bg-slate-800 text-sky-500 focus:ring-0 cursor-pointer"
                          />
                        </td>

                        <td className="py-3.5 px-4 font-medium text-white">
                          <div className="flex items-center gap-2.5">
                            {getFileIcon(doc.title)}
                            <div className="truncate max-w-xs">
                              <div className="flex items-center gap-1.5">
                                <span className="truncate text-slate-100 font-semibold">{doc.title}</span>
                                <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-sky-400 font-mono">
                                  v1
                                </span>
                              </div>
                              <div className="text-[10px] text-slate-500 font-mono truncate">{doc.id}</div>
                            </div>
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
                          {doc.tags && doc.tags.length > 0 ? (
                            <div className="flex flex-wrap gap-1 max-w-[140px]">
                              {doc.tags.slice(0, 2).map((tag) => (
                                <span
                                  key={tag}
                                  className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20"
                                >
                                  #{tag}
                                </span>
                              ))}
                              {doc.tags.length > 2 && (
                                <span className="text-[10px] text-slate-500 font-mono">
                                  +{doc.tags.length - 2}
                                </span>
                              )}
                            </div>
                          ) : (
                            <span className="text-slate-600 font-mono">—</span>
                          )}
                        </td>

                        <td className="py-3.5 px-4 text-slate-400 font-mono text-[11px]">
                          <span className="px-2 py-0.5 rounded bg-slate-800/80 border border-slate-700/60 text-slate-300">
                            {doc.source_type || "Upload"}
                          </span>
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
                          <div className="flex items-center justify-end gap-1">
                            <button
                              onClick={() => setActiveHistoryDoc(doc)}
                              title="Version History & Rollback"
                              className="p-1.5 rounded-lg border border-slate-800 hover:border-sky-500/40 hover:bg-sky-500/10 text-slate-400 hover:text-sky-300 transition-colors"
                            >
                              <History className="w-3.5 h-3.5" />
                            </button>

                            <button
                              onClick={() => setActiveShareDoc(doc)}
                              title="Share Across Workspaces"
                              className="p-1.5 rounded-lg border border-slate-800 hover:border-sky-500/40 hover:bg-sky-500/10 text-slate-400 hover:text-sky-300 transition-colors"
                            >
                              <Share2 className="w-3.5 h-3.5" />
                            </button>

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
      </div>

      {/* Bulk Action Toolbar */}
      <BulkActionToolbar
        selectedCount={selectedDocIds.size}
        onClearSelection={() => setSelectedDocIds(new Set())}
        onBulkReindex={handleBulkReindex}
        onBulkDelete={handleBulkDelete}
        onBulkMoveFolder={handleBulkMoveFolder}
        availableFolders={existingFolders}
      />

      {/* Version History Modal */}
      <VersionHistoryModal
        isOpen={!!activeHistoryDoc}
        onClose={() => setActiveHistoryDoc(null)}
        document={activeHistoryDoc}
      />

      {/* Share Document Modal */}
      <ShareDocumentModal
        isOpen={!!activeShareDoc}
        onClose={() => setActiveShareDoc(null)}
        document={activeShareDoc}
      />
    </div>
  );
}
