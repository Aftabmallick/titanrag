"use client";

import React, { useState, useEffect, useCallback } from "react";
import { GitCompare, ArrowRight, TrendingUp, TrendingDown, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";

export interface PromptDiffViewerProps {
  workspaceId: string | undefined;
  slug?: string;
  versions?: any[];
}

export function PromptDiffViewer({
  workspaceId,
  slug = "system_chat",
  versions: propVersions = [],
}: PromptDiffViewerProps) {
  const [availableVersions, setAvailableVersions] = useState<any[]>(propVersions);
  const [v1, setV1] = useState<number>(1);
  const [v2, setV2] = useState<number>(2);
  const [diffData, setDiffData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (propVersions.length > 0) {
      setAvailableVersions(propVersions);
    } else if (workspaceId) {
      api
        .listPromptVersions(workspaceId, slug)
        .then((res) => {
          if (res.versions && res.versions.length > 0) {
            setAvailableVersions(res.versions);
          }
        })
        .catch((err) => console.warn("Failed fetching prompt versions for diff:", err));
    }
  }, [propVersions, workspaceId, slug]);

  useEffect(() => {
    if (availableVersions.length >= 2) {
      // Find lowest and highest versions or standard v1 / v2
      const sorted = [...availableVersions].sort((a, b) => a.version_number - b.version_number);
      setV1(sorted[0].version_number);
      setV2(sorted[sorted.length - 1].version_number);
    } else if (availableVersions.length === 1) {
      setV1(availableVersions[0].version_number);
      setV2(availableVersions[0].version_number);
    }
  }, [availableVersions]);

  const fetchDiff = useCallback(async () => {
    if (!workspaceId || v1 === v2) {
      setDiffData(null);
      return;
    }
    setLoading(true);
    try {
      const res = await api.diffPromptVersions(workspaceId, slug, v1, v2);
      setDiffData(res);
    } catch (err: any) {
      console.warn("Could not compute prompt diff:", err?.message || err);
      setDiffData(null);
    } finally {
      setLoading(false);
    }
  }, [workspaceId, slug, v1, v2]);

  useEffect(() => {
    fetchDiff();
  }, [fetchDiff]);

  const diffLines = (diffData?.diff_unified || "").split("\n");

  return (
    <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-md space-y-5">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <GitCompare className="w-5 h-5 text-sky-400" />
          <div>
            <h3 className="text-sm font-bold text-white">Prompt Semantic & Token Diff</h3>
            <p className="text-xs text-slate-400">Inspect unified text changes and token count inflation between revisions.</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs">
            <span className="text-slate-400 px-1 font-mono">v</span>
            <select
              value={v1}
              onChange={(e) => setV1(Number(e.target.value))}
              className="bg-slate-900 text-white rounded-lg px-2 py-1 font-mono text-xs border-0 focus:ring-1 focus:ring-sky-500"
            >
              {availableVersions.map((ver) => (
                <option key={ver.version_number} value={ver.version_number}>
                  v{ver.version_number} ({ver.environment || "DEV"})
                </option>
              ))}
            </select>
            <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
            <select
              value={v2}
              onChange={(e) => setV2(Number(e.target.value))}
              className="bg-slate-900 text-white rounded-lg px-2 py-1 font-mono text-xs border-0 focus:ring-1 focus:ring-sky-500"
            >
              {availableVersions.map((ver) => (
                <option key={ver.version_number} value={ver.version_number}>
                  v{ver.version_number} ({ver.environment || "DEV"})
                </option>
              ))}
            </select>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={fetchDiff}
            disabled={loading}
            className="p-2 h-auto"
            title="Recompute Diff"
          >
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
          </Button>
        </div>
      </div>

      {/* Metrics Row */}
      {diffData && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80">
            <p className="text-[11px] font-mono text-slate-400">Baseline v{v1}</p>
            <p className="text-lg font-bold text-white font-mono mt-0.5">{diffData.old_token_count} tokens</p>
          </div>

          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80">
            <p className="text-[11px] font-mono text-slate-400">Target v{v2}</p>
            <p className="text-lg font-bold text-white font-mono mt-0.5">{diffData.new_token_count} tokens</p>
          </div>

          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-mono text-slate-400">Token Drift Delta</p>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className={`text-lg font-bold font-mono ${diffData.token_delta > 0 ? "text-amber-400" : "text-emerald-400"}`}>
                  {diffData.token_delta > 0 ? `+${diffData.token_delta}` : diffData.token_delta}
                </span>
                <span className="text-xs text-slate-400">tokens</span>
              </div>
            </div>
            {diffData.token_delta > 0 ? (
              <TrendingUp className="w-5 h-5 text-amber-400" />
            ) : (
              <TrendingDown className="w-5 h-5 text-emerald-400" />
            )}
          </div>
        </div>
      )}

      {/* Diff Code Box */}
      <div className="rounded-xl bg-slate-950 border border-slate-800/90 overflow-hidden font-mono text-xs">
        <div className="flex items-center justify-between px-4 py-2 bg-slate-900/80 border-b border-slate-800 text-slate-400 text-[11px]">
          <span>Unified Diff (v{v1} → v{v2})</span>
          <span>{slug}.jinja2</span>
        </div>

        <div className="p-4 overflow-x-auto space-y-0.5 leading-relaxed max-h-96 overflow-y-auto">
          {diffLines.length === 0 || (diffLines.length === 1 && !diffLines[0]) ? (
            <p className="text-slate-500 italic py-4 text-center">No textual differences between selected versions.</p>
          ) : (
            diffLines.map((line: string, idx: number) => {
              const isAddition = line.startsWith("+") && !line.startsWith("+++");
              const isDeletion = line.startsWith("-") && !line.startsWith("---");
              const isHeader = line.startsWith("@@") || line.startsWith("---") || line.startsWith("+++");

              return (
                <div
                  key={idx}
                  className={`flex px-2 py-0.5 rounded transition-colors ${
                    isAddition
                      ? "bg-emerald-500/15 text-emerald-300 font-medium border-l-2 border-emerald-500"
                      : isDeletion
                      ? "bg-rose-500/15 text-rose-300 font-medium border-l-2 border-rose-500"
                      : isHeader
                      ? "text-sky-400 font-bold bg-sky-500/5"
                      : "text-slate-300"
                  }`}
                >
                  <span className="w-8 text-right pr-3 text-slate-600 select-none">{idx + 1}</span>
                  <pre className="whitespace-pre-wrap flex-1">{line}</pre>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
