"use client";

import React from "react";
import { Slider } from "@/components/ui/Slider";
import { Toggle } from "@/components/ui/Toggle";
import { RAGSettingsRecord } from "@/lib/api";

export interface SearchRetrievalTabProps {
  settings: RAGSettingsRecord;
  onChange: <K extends keyof RAGSettingsRecord>(key: K, value: RAGSettingsRecord[K]) => void;
}

export function SearchRetrievalTab({ settings, onChange }: SearchRetrievalTabProps) {
  const searchStrategy = settings?.search_strategy || "hybrid";
  const hybridAlpha = typeof settings?.hybrid_alpha === "number" ? settings.hybrid_alpha : 0.7;
  const topK = typeof settings?.top_k === "number" ? settings.top_k : 40;
  const rerankTopK = typeof settings?.rerank_top_k === "number" ? settings.rerank_top_k : 5;
  const scoreThreshold = typeof settings?.score_threshold === "number" ? settings.score_threshold : 0.4;
  const parentContextEnabled = Boolean(settings?.parent_context_enabled);
  const hydeEnabled = Boolean(settings?.hyde_enabled);

  return (
    <div className="space-y-6">
      {/* Search Strategy */}
      <div className="space-y-2">
        <label className="text-xs font-semibold text-slate-300">Search Strategy</label>
        <div className="grid grid-cols-3 gap-2">
          {(["hybrid", "dense", "sparse"] as const).map((strat) => (
            <button
              key={strat}
              type="button"
              onClick={() => onChange("search_strategy", strat)}
              className={`px-3 py-2 text-xs font-semibold rounded-lg border capitalize transition-all ${
                searchStrategy === strat
                  ? "bg-sky-500/20 border-sky-500 text-sky-300 shadow-sm"
                  : "bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200"
              }`}
            >
              {strat}
            </button>
          ))}
        </div>
      </div>

      {/* Hybrid Alpha */}
      {searchStrategy === "hybrid" && (
        <div className="space-y-2">
          <div className="flex justify-between items-center text-xs">
            <span className="font-semibold text-slate-300">Hybrid Dense Alpha (α)</span>
            <span className="font-mono text-sky-400">{hybridAlpha.toFixed(2)}</span>
          </div>
          <Slider
            min={0.0}
            max={1.0}
            step={0.05}
            value={hybridAlpha}
            onChange={(val) => onChange("hybrid_alpha", val)}
          />
          <div className="flex justify-between text-[10px] text-slate-400">
            <span>0.0 (BM25 Sparse)</span>
            <span>0.5 (Balanced)</span>
            <span>1.0 (Qdrant Dense)</span>
          </div>
        </div>
      )}

      {/* Top K */}
      <div className="space-y-2">
        <div className="flex justify-between items-center text-xs">
          <span className="font-semibold text-slate-300">Initial Retrieval Pool (Top K)</span>
          <span className="font-mono text-sky-400">{topK}</span>
        </div>
        <Slider
          min={10}
          max={100}
          step={5}
          value={topK}
          onChange={(val) => onChange("top_k", val)}
        />
      </div>

      {/* Reranking Top K */}
      <div className="space-y-2">
        <div className="flex justify-between items-center text-xs">
          <span className="font-semibold text-slate-300">Reranked Output (Rerank Top K)</span>
          <span className="font-mono text-sky-400">{rerankTopK}</span>
        </div>
        <Slider
          min={1}
          max={20}
          step={1}
          value={rerankTopK}
          onChange={(val) => onChange("rerank_top_k", val)}
        />
      </div>

      {/* Score Threshold */}
      <div className="space-y-2">
        <div className="flex justify-between items-center text-xs">
          <span className="font-semibold text-slate-300">Minimum Score Threshold</span>
          <span className="font-mono text-sky-400">{scoreThreshold.toFixed(2)}</span>
        </div>
        <Slider
          min={0.1}
          max={0.9}
          step={0.05}
          value={scoreThreshold}
          onChange={(val) => onChange("score_threshold", val)}
        />
      </div>

      {/* Toggles */}
      <div className="space-y-3 pt-2 border-t border-slate-800">
        <Toggle
          label="Parent-Child Document Expansion"
          description="Returns surrounding context window around small matched chunks"
          checked={parentContextEnabled}
          onChange={(val) => onChange("parent_context_enabled", val)}
        />
        <Toggle
          label="HyDE (Hypothetical Document Embeddings)"
          description="Generates synthetic answer passage to guide dense query embedding"
          checked={hydeEnabled}
          onChange={(val) => onChange("hyde_enabled", val)}
        />
      </div>
    </div>
  );
}
