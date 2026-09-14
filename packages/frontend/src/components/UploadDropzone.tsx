"use client";

import React, { useState, useRef } from "react";
import { UploadCloud, File, CheckCircle2, AlertCircle, Loader2, X, Sparkles, ShieldAlert } from "lucide-react";
import { api, IngestionPreviewResponse } from "@/lib/api";

interface UploadDropzoneProps {
  workspaceId: string;
  onUploadSuccess: (documentId: string, filename: string) => void;
  onPreviewRequested: (data: IngestionPreviewResponse) => void;
}

export function UploadDropzone({
  workspaceId,
  onUploadSuccess,
  onPreviewRequested,
}: UploadDropzoneProps) {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [folder, setFolder] = useState("");
  const [tags, setTags] = useState("");
  const [docType, setDocType] = useState("generic");
  const [uploading, setUploading] = useState(false);
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

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFile(e.dataTransfer.files[0]);
      setErrorMsg(null);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setErrorMsg(null);
    }
  };

  const handlePreview = async () => {
    if (!selectedFile) return;
    setPreviewing(true);
    setErrorMsg(null);

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("filename", selectedFile.name);

    try {
      const previewRes = await api.previewDocument(workspaceId, formData);
      onPreviewRequested(previewRes);
    } catch (err: any) {
      setErrorMsg("Preview failed: " + err.message);
    } finally {
      setPreviewing(false);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setUploading(true);
    setErrorMsg(null);

    const formData = new FormData();
    formData.append("file", selectedFile);
    if (folder.trim()) formData.append("folder", folder.trim());
    if (tags.trim()) formData.append("tags", tags.trim());
    formData.append("doc_type", docType);

    try {
      const res = await api.uploadDocument(workspaceId, formData);
      onUploadSuccess(res.document.id, selectedFile.name);
      setSelectedFile(null);
      setFolder("");
      setTags("");
    } catch (err: any) {
      setErrorMsg(err.message || "Document upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-xl shadow-2xl">
      <div className="mb-4">
        <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
          <UploadCloud className="w-5 h-5 text-sky-400" />
          Ingest Enterprise Document
        </h2>
        <p className="text-sm text-slate-400 mt-1">
          Supports native PDFs, scanned docs (OCR), DOCX, PPTX presentations, CSV/TSV tables, and Markdown.
        </p>
      </div>

      {errorMsg && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-400">
          <ShieldAlert className="w-4 h-4 shrink-0 text-rose-400" />
          <span className="font-medium">{errorMsg}</span>
        </div>
      )}

      {/* Drop Area */}
      <div
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 transition-all cursor-pointer ${
          dragActive
            ? "border-sky-400 bg-sky-500/10"
            : "border-slate-700/80 bg-slate-950/40 hover:border-slate-600 hover:bg-slate-950/70"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          onChange={handleFileChange}
          accept=".pdf,.docx,.doc,.pptx,.ppt,.csv,.tsv,.md,.txt"
        />

        <div className="flex flex-col items-center justify-center text-center space-y-2">
          <div className="rounded-full bg-sky-500/10 p-3 text-sky-400 border border-sky-500/20">
            <UploadCloud className="w-7 h-7" />
          </div>
          <p className="text-sm font-semibold text-slate-200">
            Click to upload or drag and drop document
          </p>
          <p className="text-xs text-slate-500">
            Enforces magic-byte signature check, anti-malware scan, and hierarchical token chunking
          </p>
        </div>
      </div>

      {/* Selected File Details & Metadata Inputs */}
      {selectedFile && (
        <div className="mt-6 space-y-4 rounded-xl border border-slate-800 bg-slate-950/60 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-slate-800 p-2 text-slate-300">
                <File className="w-5 h-5 text-sky-400" />
              </div>
              <div>
                <div className="text-sm font-semibold text-white">{selectedFile.name}</div>
                <div className="text-xs text-slate-400">
                  {(selectedFile.size / 1024 / 1024).toFixed(2)} MB • {selectedFile.type || "application/octet-stream"}
                </div>
              </div>
            </div>
            <button
              onClick={() => setSelectedFile(null)}
              className="text-slate-400 hover:text-white p-1 rounded-md hover:bg-slate-800"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Folder / Namespace
              </label>
              <input
                type="text"
                placeholder="e.g. Architecture"
                value={folder}
                onChange={(e) => setFolder(e.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Tags (Comma Separated)
              </label>
              <input
                type="text"
                placeholder="e.g. core, spec, v2"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Document Type
              </label>
              <select
                value={docType}
                onChange={(e) => setDocType(e.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-sky-500"
              >
                <option value="generic">Generic Document</option>
                <option value="technical">Technical Specification</option>
                <option value="financial">Financial Report / CSV</option>
                <option value="contract">Legal Contract</option>
                <option value="presentation">Presentation Deck</option>
              </select>
            </div>
          </div>

          {/* Action Buttons: Preview Chunks + Upload */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800/80">
            <button
              onClick={handlePreview}
              disabled={previewing || uploading}
              className="flex items-center gap-2 px-4 py-2 rounded-lg border border-sky-500/30 bg-sky-500/10 hover:bg-sky-500/20 text-sky-300 text-xs font-semibold transition-colors disabled:opacity-50 cursor-pointer"
            >
              {previewing ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Parsing Chunks...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5 text-sky-400" />
                  <span>Preview Chunks</span>
                </>
              )}
            </button>

            <button
              onClick={handleUpload}
              disabled={uploading || previewing}
              className="flex items-center gap-2 px-5 py-2 rounded-lg bg-sky-500 hover:bg-sky-400 text-white text-xs font-bold shadow-lg shadow-sky-500/20 transition-all disabled:opacity-50 cursor-pointer"
            >
              {uploading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Uploading to TitanRAG...</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Ingest Document</span>
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
