"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Sparkles,
  Play,
  Plus,
  FileCheck2,
  Clock,
  CheckCircle,
  Loader2,
  RefreshCw,
  Layers,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { api } from "@/lib/api";

export function GoldenDatasetManager({
  workspaceId,
  onSelectRun,
}: {
  workspaceId: string | undefined;
  onSelectRun?: (scores: any) => void;
}) {
  const [datasets, setDatasets] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState<string | null>(null);
  const [latestRun, setLatestRun] = useState<any>(null);

  const fetchDatasetsAndRuns = useCallback(async () => {
    if (!workspaceId) return;
    setLoading(true);
    try {
      const [dsRes, runsRes] = await Promise.all([
        api.listGoldenDatasets(workspaceId).catch(() => ({ datasets: [] })),
        api.listEvaluationRuns(workspaceId).catch(() => ({ runs: [] })),
      ]);
      setDatasets(dsRes.datasets || []);
      const completedRun = (runsRes.runs || []).find((r: any) => r.status === "COMPLETED");
      if (completedRun) {
        setLatestRun(completedRun);
        if (onSelectRun && completedRun.aggregate_scores) {
          onSelectRun(completedRun.aggregate_scores);
        }
      }
    } catch {
      setDatasets([]);
    } finally {
      setLoading(false);
    }
  }, [workspaceId, onSelectRun]);

  useEffect(() => {
    fetchDatasetsAndRuns();
  }, [fetchDatasetsAndRuns]);

  const handleRunEvaluation = async (dsId: string) => {
    if (!workspaceId) return;
    setRunning(dsId);
    try {
      const res = await api.triggerEvaluationRun(workspaceId, dsId);
      const pollInterval = setInterval(async () => {
        try {
          const runDetails = await api.getEvaluationRun(workspaceId, res.run_id);
          if (runDetails.status === "COMPLETED" || runDetails.status === "FAILED") {
            clearInterval(pollInterval);
            setLatestRun(runDetails);
            if (onSelectRun && runDetails.aggregate_scores) {
              onSelectRun(runDetails.aggregate_scores);
            }
            setRunning(null);
          }
        } catch {
          clearInterval(pollInterval);
          setRunning(null);
        }
      }, 1500);

      // Max timeout of 15 seconds for polling
      setTimeout(() => {
        clearInterval(pollInterval);
        setRunning(null);
      }, 15000);
    } catch (err: any) {
      alert("Failed triggering evaluation: " + (err.message || err));
      setRunning(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-sky-400" />
          <h3 className="text-sm font-bold text-white">Curated Golden Datasets</h3>
        </div>
        <button
          onClick={fetchDatasetsAndRuns}
          disabled={loading}
          className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {datasets.length === 0 && !loading ? (
        <EmptyState
          icon={<Layers className="w-6 h-6 text-sky-400" />}
          title="No Golden Datasets Found"
          description="Create or promote evaluation datasets to benchmark Faithfulness, Answer Relevancy, and IR precision."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4">
        {datasets.map((ds) => (
          <div
            key={ds.id}
            className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-md flex flex-col sm:flex-row sm:items-center justify-between gap-4"
          >
            <div className="space-y-1 max-w-xl">
              <div className="flex items-center gap-2">
                <span className="font-bold text-white text-sm">{ds.name}</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-800 text-slate-300">
                  {ds.item_count} test items
                </span>
              </div>
              <p className="text-xs text-slate-400">{ds.description}</p>
              <div className="flex flex-wrap gap-1 mt-2">
                {ds.tags?.map((t: string, idx: number) => (
                  <span key={idx} className="text-[10px] px-2 py-0.5 rounded bg-slate-800/80 text-sky-400 font-mono">
                    #{t}
                  </span>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Button
                variant="primary"
                size="sm"
                onClick={() => handleRunEvaluation(ds.id)}
                disabled={running === ds.id}
                className="flex items-center gap-1.5"
              >
                {running === ds.id ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Evaluating...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5 fill-current" />
                    <span>Run Benchmark</span>
                  </>
                )}
              </Button>
            </div>
          </div>
        ))}
      </div>
      )}
    </div>
  );
}
