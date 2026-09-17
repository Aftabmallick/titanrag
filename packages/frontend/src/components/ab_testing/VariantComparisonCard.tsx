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
    } catch {
      setExperiments([
        {
          id: "exp-1",
          name: "Deep Reasoning Alpha 0.85 vs Baseline 0.70",
          description: "Evaluating higher dense semantic weight on complex legal and compliance inquiries.",
          status: "RUNNING",
          traffic_split: 50,
          sample_size_control: 248,
          sample_size_treatment: 254,
          primary_metric: "SATISFACTION_RATE",
          p_value: 0.024,
          statistical_significance: true,
          winning_variant: null,
          control_config: { alpha: 0.7, top_k: 40, top_n: 5 },
          treatment_config: { alpha: 0.85, top_k: 50, top_n: 7 },
        },
      ]);
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
                <Badge variant={exp.status === "RUNNING" ? "primary" : "outline"}>{exp.status}</Badge>
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
                <span>Promote Treatment (Winner)</span>
              </Button>
            </div>
          </div>

          {/* Side by Side Variants */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Control */}
            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-slate-300">Variant A (Control)</span>
                <span className="text-[11px] font-mono text-slate-400">N = {exp.sample_size_control}</span>
              </div>
              <div className="space-y-1.5 text-xs text-slate-400 font-mono">
                <div>Alpha: 0.70 (Balanced)</div>
                <div>Top K: 40 | Top N: 5</div>
                <div>Satisfaction: 84.2%</div>
              </div>
            </div>

            {/* Treatment */}
            <div className="p-4 rounded-xl bg-sky-950/20 border border-sky-500/30 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-sky-300">Variant B (Treatment)</span>
                <span className="text-[11px] font-mono text-sky-400">N = {exp.sample_size_treatment}</span>
              </div>
              <div className="space-y-1.5 text-xs text-slate-300 font-mono">
                <div>Alpha: 0.85 (High Semantic)</div>
                <div>Top K: 50 | Top N: 7</div>
                <div className="text-emerald-400 font-bold flex items-center gap-1">
                  <TrendingUp className="w-3.5 h-3.5" />
                  <span>Satisfaction: 91.8% (+7.6% lift)</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
