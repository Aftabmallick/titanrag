"use client";

import React, { useState } from "react";
import { X, Layers, Sparkles, Hash, FileText, CheckCircle2, Binary } from "lucide-react";
import { IngestionPreviewResponse, IngestionPreviewChunk } from "@/lib/api";

interface IngestionPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  previewData: IngestionPreviewResponse | null;
  loading?: boolean;
  onApprove?: () => void;
  onDiscard?: () => void;
}

export function IngestionPreviewModal({
  isOpen,
  onClose,
  previewData,
  loading = false,
  onApprove,
  onDiscard,
}: IngestionPreviewModalProps) {
  const [activeTab, setActiveTab] = useState<"all" | "parents" | "children">("all");

  if (!isOpen) return null;

  const chunks = previewData?.sample_chunks || [];
  const filteredChunks = chunks.filter((c) => {
    if (activeTab === "parents") return c.chunk_type === "PARENT";
    if (activeTab === "children") return c.chunk_type === "CHILD";
    return true;
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-md p-4 animate-in fade-in duration-200">
      <div className="flex flex-col w-full max-w-4xl max-h-[85vh] rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/50">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white tracking-tight flex items-center gap-2">
                Hierarchical Ingestion Preview
                {previewData && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
                    {previewData.filename}
                  </span>
                )}
              </h3>
              <p className="text-xs text-slate-400">
                Real-time parsing, context prepending, and dual-tree token partitioning
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Top Metrics Row */}
        {previewData && (
          <div className="grid grid-cols-3 gap-3 p-4 bg-slate-950/40 border-b border-slate-800">
            <div className="px-4 py-2.5 rounded-xl border border-slate-800/80 bg-slate-900/40">
              <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Parent Chunks</div>
              <div className="text-2xl font-black text-white">{previewData.total_parent_chunks}</div>
              <div className="text-[10px] text-slate-500">~1000 tokens (Context Store)</div>
            </div>

            <div className="px-4 py-2.5 rounded-xl border border-slate-800/80 bg-slate-900/40">
              <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Child Chunks</div>
              <div className="text-2xl font-black text-sky-400">{previewData.total_child_chunks}</div>
              <div className="text-[10px] text-slate-500">~200-300 tokens (Retrieval Target)</div>
            </div>

            <div className="px-4 py-2.5 rounded-xl border border-slate-800/80 bg-slate-900/40">
              <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Sample Elements</div>
              <div className="text-2xl font-black text-indigo-400">{chunks.length}</div>
              <div className="text-[10px] text-slate-500">Dual-Tree Verified Sample</div>
            </div>
          </div>
        )}

        {/* Tab Filter Bar */}
        <div className="flex items-center justify-between px-6 py-2.5 border-b border-slate-800 bg-slate-900/30">
          <div className="flex gap-2">
            <button
              onClick={() => setActiveTab("all")}
              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
                activeTab === "all"
                  ? "bg-sky-500/20 text-sky-300 border border-sky-500/30"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              All Samples ({chunks.length})
            </button>
            <button
              onClick={() => setActiveTab("parents")}
              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
                activeTab === "parents"
                  ? "bg-sky-500/20 text-sky-300 border border-sky-500/30"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Parent Chunks
            </button>
            <button
              onClick={() => setActiveTab("children")}
              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
                activeTab === "children"
                  ? "bg-sky-500/20 text-sky-300 border border-sky-500/30"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Child Chunks (Enriched)
            </button>
          </div>

          <div className="flex items-center gap-2 text-[11px] text-slate-500 font-mono">
            <Binary className="w-3.5 h-3.5 text-emerald-400" />
            <span>Dual-Vector Ready</span>
          </div>
        </div>

        {/* Chunk Content Cards */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-16 text-slate-400 space-y-3">
              <div className="w-8 h-8 rounded-full border-2 border-sky-500 border-t-transparent animate-spin" />
              <p className="text-sm">Executing parser, redactor, and hierarchical chunker...</p>
            </div>
          ) : filteredChunks.length === 0 ? (
            <div className="text-center py-12 text-slate-500 text-sm">
              No chunks to preview. Click &quot;Preview Chunks&quot; on a document or file.
            </div>
          ) : (
            filteredChunks.map((chunk) => {
              const isParent = chunk.chunk_type === "PARENT";
              return (
                <div
                  key={chunk.index}
                  className={`p-4 rounded-xl border transition-all ${
                    isParent
                      ? "border-indigo-500/30 bg-indigo-950/20 shadow-sm shadow-indigo-500/5"
                      : "border-sky-500/30 bg-sky-950/20 shadow-sm shadow-sky-500/5"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border font-mono ${
                          isParent
                            ? "border-indigo-500/40 bg-indigo-500/20 text-indigo-300"
                            : "border-sky-500/40 bg-sky-500/20 text-sky-300"
                        }`}
                      >
                        {isParent ? "PARENT CONTAINER" : "CHILD CHUNK"} #{chunk.index}
                      </span>
                      {chunk.section_heading && (
                        <span className="text-xs text-slate-300 font-medium truncate max-w-sm">
                          📌 {chunk.section_heading}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-slate-400 font-mono">
                      <Hash className="w-3 h-3 text-slate-500" />
                      <span>{chunk.token_count} tokens</span>
                    </div>
                  </div>

                  {/* Context Prefix Badge if Child */}
                  {!isParent && chunk.context_prefix && (
                    <div className="mb-3 p-2.5 rounded-lg border border-amber-500/30 bg-amber-500/10 text-xs text-amber-200 flex items-start gap-2">
                      <Sparkles className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                      <div>
                        <strong className="text-amber-300 font-semibold">LLM Context Prefix: </strong>
                        {chunk.context_prefix}
                      </div>
                    </div>
                  )}

                  {/* Chunk Text */}
                  <pre className="text-xs text-slate-200 font-mono bg-slate-950/60 p-3 rounded-lg border border-slate-800/80 whitespace-pre-wrap break-words leading-relaxed">
                    {chunk.content}
                  </pre>
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-3 border-t border-slate-800 bg-slate-900/80">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>Ready for Transactional Outbox projection to Qdrant</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                if (onDiscard) onDiscard();
                onClose();
              }}
              className="px-3.5 py-1.5 rounded-xl border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition-colors"
            >
              Discard
            </button>
            {onApprove && (
              <button
                onClick={() => {
                  onApprove();
                  onClose();
                }}
                className="px-4 py-1.5 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white text-xs font-bold shadow-md shadow-sky-500/20 transition-all cursor-pointer"
              >
                Approve & Embed Chunks
              </button>
            )}
            {!onApprove && (
              <button
                onClick={onClose}
                className="px-4 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition-colors"
              >
                Close Preview
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
