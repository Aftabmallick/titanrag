"use client";

import React from "react";
import { Slider } from "@/components/ui/Slider";
import { Toggle } from "@/components/ui/Toggle";
import { RAGSettingsRecord } from "@/lib/api";

export interface SemanticCacheTabProps {
  settings: RAGSettingsRecord;
  onChange: <K extends keyof RAGSettingsRecord>(key: K, value: RAGSettingsRecord[K]) => void;
}

export function SemanticCacheTab({ settings, onChange }: SemanticCacheTabProps) {
  const semanticCacheEnabled = Boolean(settings?.semantic_cache_enabled);
  const cacheSimilarityThreshold =
    typeof settings?.cache_similarity_threshold === "number" ? settings.cache_similarity_threshold : 0.95;
  const cacheTtlSeconds = typeof settings?.cache_ttl_seconds === "number" ? settings.cache_ttl_seconds : 86400;
  const ttlHours = Math.max(1, Math.round(cacheTtlSeconds / 3600));

  return (
    <div className="space-y-6">
      <Toggle
        label="Enable Redis Semantic Caching"
        description="Caches query embeddings with ACL salt partitioning to return instant responses for semantically identical questions"
        checked={semanticCacheEnabled}
        onChange={(val) => onChange("semantic_cache_enabled", val)}
      />

      {semanticCacheEnabled && (
        <>
          {/* Similarity Threshold */}
          <div className="space-y-2">
            <div className="flex justify-between items-center text-xs">
              <span className="font-semibold text-slate-300">Semantic Cosine Threshold</span>
              <span className="font-mono text-emerald-400">
                {cacheSimilarityThreshold.toFixed(2)}
              </span>
            </div>
            <Slider
              min={0.8}
              max={0.99}
              step={0.01}
              value={cacheSimilarityThreshold}
              onChange={(val) => onChange("cache_similarity_threshold", val)}
            />
            <div className="flex justify-between text-[10px] text-slate-400">
              <span>0.80 (Loose / Broad Matches)</span>
              <span>0.95 (Recommended)</span>
              <span>0.99 (Near Exact)</span>
            </div>
          </div>

          {/* TTL */}
          <div className="space-y-2">
            <div className="flex justify-between items-center text-xs">
              <span className="font-semibold text-slate-300">Cache TTL (Hours)</span>
              <span className="font-mono text-emerald-400">
                {ttlHours}h
              </span>
            </div>
            <Slider
              min={1}
              max={168}
              step={1}
              value={ttlHours}
              onChange={(val) => onChange("cache_ttl_seconds", val * 3600)}
            />
            <div className="flex justify-between text-[10px] text-slate-400">
              <span>1h (Rapid Invalidation)</span>
              <span>24h (1 Day)</span>
              <span>168h (7 Days)</span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
