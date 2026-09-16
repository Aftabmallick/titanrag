"use client";

import React, { useState, useRef } from "react";
import {
  UploadCloud,
  FileText,
  FileSpreadsheet,
  Presentation,
  FileCode,
  CheckCircle2,
  AlertCircle,
  Loader2,
  X,
  Sparkles,
  Layers,
  Trash2,
} from "lucide-react";
import { api, IngestionPreviewResponse } from "@/lib/api";

interface QueuedFile {
  id: string;
  file: File;
  progress: number;
  status: "pending" | "uploading" | "done" | "error";
  error?: string;
}

interface UploadDropzoneProps {
  workspaceId: string;
  onUploadSuccess: (documentId: string, filename: string) => void;
  onPreviewRequested: (data: IngestionPreviewResponse) => void;
}

function getFileIcon(filename: string) {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".pdf")) return <FileText className="w-4 h-4 text-rose-400" />;
  if (lower.endsWith(".csv") || lower.endsWith(".tsv")) return <FileSpreadsheet className="w-4 h-4 text-emerald-400" />;
  if (lower.endsWith(".pptx") || lower.endsWith(".ppt")) return <Presentation className="w-4 h-4 text-amber-400" />;
  if (lower.endsWith(".md") || lower.endsWith(".txt")) return <FileCode className="w-4 h-4 text-sky-400" />;
  return <FileText className="w-4 h-4 text-slate-400" />;
}

function formatBytes(bytes: number) {
  if (!bytes) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

export function UploadDropzone({
  workspaceId,
  onUploadSuccess,
  onPreviewRequested,
}: UploadDropzoneProps) {
  const [dragActive, setDragActive] = useState(false);
  const [fileQueue, setFileQueue] = useState<QueuedFile[]>([]);
  const [folder, setFolder] = useState("");
  const [tags, setTags] = useState("");
  const [docType, setDocType] = useState("generic");
  const [previewing, setPreviewing] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const addFilesToQueue = (files: FileList | File[]) => {
    const newItems: QueuedFile[] = Array.from(files).map((file) => ({
      id: Math.random().toString(36).substring(2, 9),
      file,
      progress: 0,
      status: "pending",
    }));
    setFileQueue((prev) => [...prev, ...newItems]);
    setErrorMsg(null);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      addFilesToQueue(e.dataTransfer.files);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addFilesToQueue(e.target.files);
    }
  };

  const removeFileFromQueue = (id: string) => {
    setFileQueue((prev) => prev.filter((f) => f.id !== id));
  };

  const handlePreviewFirst = async () => {
    if (fileQueue.length === 0) return;
    const target = fileQueue[0];
    setPreviewing(true);
    setErrorMsg(null);

    const formData = new FormData();
    formData.append("file", target.file);
    formData.append("filename", target.file.name);

    try {
      const previewRes = await api.previewDocument(workspaceId, formData);
      onPreviewRequested(previewRes);
    } catch (err: any) {
      setErrorMsg("Preview failed: " + err.message);
    } finally {
      setPreviewing(false);
    }
  };

  const handleUploadAll = async () => {
    if (fileQueue.length === 0) return;
    setErrorMsg(null);

    for (const item of fileQueue) {
      if (item.status === "done") continue;

      setFileQueue((prev) =>
        prev.map((f) => (f.id === item.id ? { ...f, status: "uploading", progress: 25 } : f))
      );

      const formData = new FormData();
      formData.append("file", item.file);
      if (folder.trim()) formData.append("folder", folder.trim());
      if (tags.trim()) formData.append("tags", tags.trim());
      formData.append("doc_type", docType);

      try {
        setFileQueue((prev) =>
          prev.map((f) => (f.id === item.id ? { ...f, progress: 65 } : f))
        );
        const res = await api.uploadDocument(workspaceId, formData);
        setFileQueue((prev) =>
          prev.map((f) => (f.id === item.id ? { ...f, status: "done", progress: 100 } : f))
        );
        onUploadSuccess(res.document.id, item.file.name);
      } catch (err: any) {
        setFileQueue((prev) =>
          prev.map((f) =>
            f.id === item.id ? { ...f, status: "error", error: err.message } : f
          )
        );
      }
    }
  };

  const isUploadingAny = fileQueue.some((f) => f.status === "uploading");
  const pendingCount = fileQueue.filter((f) => f.status === "pending").length;

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-xl shadow-2xl space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <UploadCloud className="w-5 h-5 text-sky-400" />
            <span>Ingest Knowledge Documents</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Enterprise pipeline with Docling parsing, PII redaction, hierarchical chunking, and Transactional Outbox.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {fileQueue.length > 0 && (
            <button
              onClick={handlePreviewFirst}
              disabled={previewing || isUploadingAny}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-sky-500/30 bg-sky-500/10 text-sky-300 text-xs font-semibold hover:bg-sky-500/20 transition-all disabled:opacity-50 cursor-pointer"
            >
              {previewing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Layers className="w-3.5 h-3.5" />}
              <span>Preview Chunks</span>
            </button>
          )}

          <button
            onClick={handleUploadAll}
            disabled={fileQueue.length === 0 || isUploadingAny || pendingCount === 0}
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white text-xs font-bold shadow-md shadow-sky-500/20 transition-all disabled:opacity-40 cursor-pointer"
          >
            {isUploadingAny ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
            <span>Upload {pendingCount > 0 ? `(${pendingCount})` : ""}</span>
          </button>
        </div>
      </div>

      {/* Drag & Drop Area */}
      <div
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`relative flex flex-col items-center justify-center p-8 rounded-2xl border-2 border-dashed transition-all cursor-pointer ${
          dragActive
            ? "border-sky-400 bg-sky-500/10 scale-[1.01]"
            : "border-slate-800 hover:border-slate-700 bg-slate-950/40 hover:bg-slate-900/40"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          onChange={handleFileChange}
          accept=".pdf,.docx,.txt,.md,.csv,.pptx"
          className="hidden"
        />

        <div className="w-12 h-12 rounded-2xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 mb-3 shadow-md">
          <UploadCloud className="w-6 h-6" />
        </div>

        <h3 className="text-sm font-bold text-slate-100">
          Drop enterprise documents here, or <span className="text-sky-400">browse files</span>
        </h3>
        <p className="text-xs text-slate-500 mt-1">
          Supports multi-file PDF, DOCX, CSV, PPTX, TXT, MD (up to 100MB per document)
        </p>
      </div>

      {/* Queue List of Selected Files */}
      {fileQueue.length > 0 && (
        <div className="space-y-2 pt-1">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-300">
            <span>Selected Files Queue ({fileQueue.length})</span>
            <button
              onClick={() => setFileQueue([])}
              className="text-[11px] text-slate-500 hover:text-rose-400 transition-colors"
            >
              Clear Queue
            </button>
          </div>

          <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
            {fileQueue.map((item) => (
              <div
                key={item.id}
                className="p-3 rounded-xl border border-slate-800 bg-slate-950/60 flex items-center justify-between gap-3 text-xs"
              >
                <div className="flex items-center gap-2.5 min-w-0 flex-1">
                  {getFileIcon(item.file.name)}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-slate-200 truncate">{item.file.name}</span>
                      <span className="font-mono text-[10px] text-slate-500 shrink-0">
                        {formatBytes(item.file.size)}
                      </span>
                    </div>

                    {/* Progress bar */}
                    {item.status === "uploading" && (
                      <div className="h-1.5 w-full bg-slate-800 rounded-full mt-1.5 overflow-hidden">
                        <div
                          className="h-full bg-sky-400 rounded-full transition-all duration-300"
                          style={{ width: `${item.progress}%` }}
                        />
                      </div>
                    )}
                    {item.error && (
                      <span className="text-[10px] text-rose-400 mt-1 block truncate">
                        {item.error}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {item.status === "uploading" && <Loader2 className="w-4 h-4 text-sky-400 animate-spin" />}
                  {item.status === "done" && <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
                  {item.status === "error" && <AlertCircle className="w-4 h-4 text-rose-400" />}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeFileFromQueue(item.id);
                    }}
                    className="p-1 rounded text-slate-500 hover:text-rose-400 hover:bg-slate-800"
                    title="Remove from queue"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Metadata Configuration */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
        <div className="space-y-1">
          <label className="text-xs font-semibold text-slate-300">Folder / Namespace</label>
          <input
            type="text"
            placeholder="e.g. Legal, Finance"
            value={folder}
            onChange={(e) => setFolder(e.target.value)}
            className="w-full px-3 py-1.5 rounded-xl bg-slate-950/80 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
          />
        </div>

        <div className="space-y-1">
          <label className="text-xs font-semibold text-slate-300">Tags (comma-separated)</label>
          <input
            type="text"
            placeholder="e.g. 2024, confidential"
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            className="w-full px-3 py-1.5 rounded-xl bg-slate-950/80 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
          />
        </div>

        <div className="space-y-1">
          <label className="text-xs font-semibold text-slate-300">Document Type</label>
          <select
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
            className="w-full px-3 py-1.5 rounded-xl bg-slate-950/80 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-sky-500 cursor-pointer"
          >
            <option value="generic">Generic Document</option>
            <option value="contract">Contract / NDA</option>
            <option value="financial">Financial Report</option>
            <option value="technical">Technical Architecture</option>
            <option value="policy">Enterprise Policy</option>
          </select>
        </div>
      </div>

      {errorMsg && (
        <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-400 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}
    </div>
  );
}
