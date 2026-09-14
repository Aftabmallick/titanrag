"use client";

import React, { useState } from "react";
import { X, Layers, Sparkles, Hash, FileText, CheckCircle2 } from "lucide-react";

interface IngestionPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  documentTitle: string;
}

export function IngestionPreviewModal({
  isOpen,
  onClose,
  documentTitle,
}: IngestionPreviewModalProps) {
  const [activeTab, setActiveTab] = useState<"all" | "parents" | "children">("all");

  if (!isOpen) return null;

  const mockPreviewChunks = [
    {
      id: "parent-1",
      is_parent: true,
      index: 0,
      token_count: 1042,
      section: "System Architecture > Overview",
      content:
        "# System Specifications\nTitanRAG is an enterprise multi-tenant hybrid retrieval-augmented generation engine with defense-in-depth isolation, Transactional Outbox vector projections, and real-time streaming citations.",
    },
    {
      id: "child-1",
      is_parent: false,
      parent_id: "parent-1",
      index: 1,
      token_count: 248,
      section: "System Architecture > Overview",
      context_prefix: "Context: This excerpt details TitanRAG core system specifications and transactional outbox guarantees.",
      content:
        "TitanRAG treats PostgreSQL as the single Source of Record and Qdrant strictly as an Ephemeral Projection Index. Worker crashes produce zero orphaned vectors.",
    },
    {
      id: "child-2",
      is_parent: false,
      parent_id: "parent-1",
      index: 2,
      token_count: 186,
      section: "System Architecture > Dual Vector Pipeline",
      context_prefix: "Context: This excerpt explains the dual vector projection combining dense embeddings with BM25 sparse vectors.",
      content:
        "| Vector Type | Dimensions | Engine |\n| --- | --- | --- |\n| Dense | 1536 | HNSW INT8 |\n| Sparse | Vocab-wide | BM25 IDF |",
    },
  ];

  const filteredChunks = mockPreviewChunks.filter((c) => {
    if (activeTab === "parents") return c.is_parent;
    if (activeTab === "children") return !c.is_parent;
    return true;
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-full max-w-3xl rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-800 bg-slate-950/60">
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-sky-400" />
            <h3 className="text-lg font-bold text-white">Hierarchical Chunks Preview</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg bg-slate-800 text-slate-400 hover:text-white"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Sub-header info */}
        <div className="px-6 py-3 bg-slate-900/40 border-b border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-slate-500" />
            <span className="text-slate-200 font-medium">{documentTitle}</span>
          </div>
          <div className="flex items-center gap-3">
            <span>Parent Chunks: <strong className="text-sky-400">1</strong></span>
            <span>Child Chunks: <strong className="text-indigo-400">2</strong></span>
            <span>Avg Tokens: <strong className="text-emerald-400">492</strong></span>
          </div>
        </div>

        {/* Tab Filters */}
        <div className="flex border-b border-slate-800 bg-slate-950/30 px-6 pt-3 gap-3">
          {(["all", "parents", "children"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`pb-2 text-xs font-semibold uppercase tracking-wider transition-all border-b-2 ${
                activeTab === tab
                  ? "border-sky-400 text-sky-400"
                  : "border-transparent text-slate-500 hover:text-slate-300"
              }`}
            >
              {tab === "all" ? "All Chunks" : tab === "parents" ? "Parents (1024 tok)" : "Children (256 tok)"}
            </button>
          ))}
        </div>

        {/* Content list */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {filteredChunks.map((chunk) => (
            <div
              key={chunk.id}
              className={`rounded-xl border p-4 space-y-2 transition-all ${
                chunk.is_parent
                  ? "border-sky-500/30 bg-sky-500/5 shadow-sm shadow-sky-500/10"
                  : "border-indigo-500/30 bg-indigo-500/5 shadow-sm shadow-indigo-500/10"
              }`}
            >
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span
                    className={`px-2 py-0.5 rounded font-mono font-bold ${
                      chunk.is_parent
                        ? "bg-sky-500/20 text-sky-300"
                        : "bg-indigo-500/20 text-indigo-300"
                    }`}
                  >
                    #{chunk.index} • {chunk.is_parent ? "PARENT" : "CHILD"}
                  </span>
                  <span className="text-slate-400">{chunk.section}</span>
                </div>
                <span className="flex items-center gap-1 text-slate-400">
                  <Hash className="w-3 h-3 text-slate-500" />
                  {chunk.token_count} tokens
                </span>
              </div>

              {chunk.context_prefix && (
                <div className="flex items-start gap-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 p-2 text-xs text-amber-300">
                  <Sparkles className="w-3.5 h-3.5 mt-0.5 shrink-0 text-amber-400" />
                  <span>{chunk.context_prefix}</span>
                </div>
              )}

              <p className="text-xs font-mono text-slate-300 leading-relaxed whitespace-pre-wrap bg-slate-950/60 p-3 rounded-lg border border-slate-800">
                {chunk.content}
              </p>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/80 flex justify-end">
          <button
            onClick={onClose}
            className="rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700 hover:text-white"
          >
            Close Preview
          </button>
        </div>
      </div>
    </div>
  );
}
