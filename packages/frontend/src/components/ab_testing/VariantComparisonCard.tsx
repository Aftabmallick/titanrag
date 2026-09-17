"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Split,
  Trophy,
  CheckCircle2,
  AlertTriangle,
  Play,
  Pause,
  RotateCcw,
  Sparkles,
  Loader2,
  TrendingUp,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { api } from "@/lib/api";

export function VariantComparisonCard({ workspaceId }: { workspaceId: string | undefined }) {
  const [experiments, setExperiments] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  const fetchExperiments = useCallback(async () => {
    if (!workspaceId) return;
    setLoading(true);
    try {
      const res = await api.listExperiments(workspaceId);
      setExperiments(res.experiments || []);
    } catch (err: any) {
      console.warn("Failed fetching experiments:", err?.message || err);
      setExperiments([]);
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    fetchExperiments();
  }, [fetchExperiments]);

  const handleConclude = async (expId: string, winner: "CONTROL" | "TREATMENT") => {
    if (!workspaceId) return;
    setActionLoading(true);
    try {
      await api.concludeExperiment(workspaceId, expId, {
        winning_variant: winner,
        apply_to_workspace_settings: winner === "TREATMENT",
      });
      await fetchExperiments();
    } catch (err: any) {
      alert("Failed concluding experiment: " + (err.message || err));
    } finally {
      setActionLoading(false);
    }
  };

  if (!loading && experiments.length === 0) {
    return (
      <EmptyState
        icon={<Split className="w-6 h-6" />}
        title="No Active A/B Experiments"
        description="Launch a retrieval experiment to benchmark dense vs sparse hybrid weights and re-ranking algorithms against live queries."
      />
    );
  }

  return (
    <div className="space-y-6">
      {experiments.map((exp) => (
        <div
          key={exp.id}
          className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-md space-y-6"
        >
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-white text-base">{exp.name}</span>
                <Badge variant={exp.status === "RUNNING" ? "primary" : exp.status === "COMPLETED" ? "success" : "outline"}>
                  {exp.status}
                </Badge>
                {exp.statistical_significance && (
                  <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                    <CheckCircle2 className="w-3 h-3" />
                    <span>Statistically Significant (p = {exp.p_value})</span>
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 mt-1">{exp.description}</p>
            </div>

            <div className="flex items-center gap-2">
              {exp.winning_variant ? (
                <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-semibold">
                  <Trophy className="w-3.5 h-3.5" />
                  <span>Concluded: Winner is {exp.winning_variant}</span>
                </div>
              ) : (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleConclude(exp.id, "CONTROL")}
                    disabled={actionLoading || exp.status !== "RUNNING"}
                    className="text-xs"
                  >
                    Keep Control
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => handleConclude(exp.id, "TREATMENT")}
                    disabled={actionLoading || exp.status !== "RUNNING"}
                    className="text-xs flex items-center gap-1.5"
                  >
                    <Trophy className="w-3.5 h-3.5 text-amber-300" />
                    <span>Promote Treatment</span>
                  </Button>
                </>
              )}
            </div>
          </div>

          {/* Side by Side Variants */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Control */}
            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-slate-300">Variant A (Control)</span>
                <span className="text-[11px] font-mono text-slate-400">N = {exp.sample_size_control ?? 0}</span>
              </div>
              <div className="space-y-1.5 text-xs text-slate-400 font-mono">
                <div>Alpha: {exp.control_config?.alpha ?? "0.70 (Balanced)"}</div>
                <div>Top K: {exp.control_config?.top_k ?? 40}</div>
                {exp.control_config?.rerank_model && <div>Reranker: {exp.control_config.rerank_model}</div>}
                {exp.winning_variant === "CONTROL" && (
                  <div className="text-emerald-400 font-bold flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Active Production Baseline</span>
                  </div>
                )}
              </div>
            </div>

            {/* Treatment */}
            <div className="p-4 rounded-xl bg-sky-950/20 border border-sky-500/30 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-sky-300">Variant B (Treatment)</span>
                <span className="text-[11px] font-mono text-sky-400">N = {exp.sample_size_treatment ?? 0}</span>
              </div>
              <div className="space-y-1.5 text-xs text-slate-300 font-mono">
                <div>Alpha: {exp.treatment_config?.alpha ?? "0.50"}</div>
                <div>Top K: {exp.treatment_config?.top_k ?? 40}</div>
                {exp.treatment_config?.rerank_model && <div>Reranker: {exp.treatment_config.rerank_model}</div>}
                {exp.winning_variant === "TREATMENT" ? (
                  <div className="text-emerald-400 font-bold flex items-center gap-1">
                    <Trophy className="w-3.5 h-3.5 text-amber-300" />
                    <span>Winning Variant (Promoted to Prod)</span>
                  </div>
                ) : exp.statistical_significance ? (
                  <div className="text-emerald-400 font-bold flex items-center gap-1">
                    <TrendingUp className="w-3.5 h-3.5" />
                    <span>Statistically Significant (p = {exp.p_value})</span>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
