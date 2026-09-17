"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  ThumbsUp,
  ThumbsDown,
  Sparkles,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  FileText,
  Loader2,
  RefreshCw,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";

export function FeedbackTriageTable({ workspaceId }: { workspaceId: string | undefined }) {
  const [items, setItems] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchFeedback = useCallback(async () => {
    if (!workspaceId) return;
    setLoading(true);
    try {
      const res = await api.listFeedback(workspaceId, { limit: 50 });
      setItems(res.items || []);
      setStats(res.statistics || null);
    } catch {
      // Fallback mock for demo if backend is offline
      setItems([
        {
          id: "fb-1",
          rating: -1,
          comment: "Citation [^1] states 2023 revenue instead of Q3 2024 revenue numbers.",
          corrected_answer: "Q3 2024 revenue was $14.2M, an increase of 18% YoY.",
          citation_issues: [{ citation_id: "[^1]", issue_type: "outdated_page", comment: "Wrong fiscal year" }],
          triage_status: "NEW",
          created_at: new Date().toISOString(),
        },
        {
          id: "fb-2",
          rating: 1,
          comment: "Extremely fast and accurate summary of the termination clause.",
          citation_issues: [],
          triage_status: "TRIAGED",
          created_at: new Date(Date.now() - 3600000).toISOString(),
        },
      ]);
      setStats({
        total: 2,
        positive_count: 1,
        negative_count: 1,
        satisfaction_rate_percent: 50.0,
      });
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    fetchFeedback();
  }, [fetchFeedback]);

  const handlePromote = async (fbId: string) => {
    if (!workspaceId) return;
    setActionLoading(fbId);
    try {
      await api.promoteFeedbackToGolden(workspaceId, fbId);
      await fetchFeedback();
    } catch (err: any) {
      alert("Failed promoting to golden dataset: " + (err.message || err));
    } finally {
      setActionLoading(null);
    }
  };

  const handleTriage = async (fbId: string, status: string) => {
    if (!workspaceId) return;
    setActionLoading(fbId);
    try {
      await api.updateFeedbackTriage(workspaceId, fbId, status);
      await fetchFeedback();
    } catch (err: any) {
      alert("Failed updating triage status: " + (err.message || err));
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-md">
          <p className="text-xs text-slate-400 font-medium">Satisfaction Rate</p>
          <p className="text-2xl font-black text-emerald-400 mt-1">
            {stats ? `${stats.satisfaction_rate_percent}%` : "--"}
          </p>
        </div>
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-md">
          <p className="text-xs text-slate-400 font-medium">Total Feedback</p>
          <p className="text-2xl font-black text-white mt-1">{stats ? stats.total : "--"}</p>
        </div>
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-md">
          <p className="text-xs text-slate-400 font-medium">Positive Answers</p>
          <p className="text-2xl font-black text-sky-400 mt-1">{stats ? stats.positive_count : "--"}</p>
        </div>
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-md">
          <p className="text-xs text-slate-400 font-medium">Flagged for Triage</p>
          <p className="text-2xl font-black text-rose-400 mt-1">{stats ? stats.negative_count : "--"}</p>
        </div>
      </div>

      {/* Table Card */}
      <div className="rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-md overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-white">Continuous Feedback & Citation Triage Queue</h3>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full border border-sky-500/30 bg-sky-500/10 text-sky-400">
              Evaluation Flywheel Active
            </span>
          </div>
          <button
            onClick={fetchFeedback}
            disabled={loading}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950/60 text-slate-400 uppercase font-mono tracking-wider text-[10px]">
              <tr>
                <th className="px-6 py-3">Rating</th>
                <th className="px-6 py-3">User Comment & Citation Flags</th>
                <th className="px-6 py-3">Corrected Ground Truth</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3 text-right">Flywheel Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {items.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-slate-500">
                    No user feedback recorded yet. Feedback from chat will automatically stream here.
                  </td>
                </tr>
              ) : (
                items.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-800/30 transition">
                    <td className="px-6 py-4">
                      {item.rating > 0 ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-semibold">
                          <ThumbsUp className="w-3 h-3" /> Positive
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-rose-500/10 border border-rose-500/30 text-rose-400 font-semibold">
                          <ThumbsDown className="w-3 h-3" /> Negative
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 max-w-md">
                      <p className="font-medium text-slate-200">{item.comment || "No comment provided"}</p>
                      {item.citation_issues && item.citation_issues.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mt-2">
                          {item.citation_issues.map((ci: any, idx: number) => (
                            <span
                              key={idx}
                              className="text-[10px] px-2 py-0.5 rounded bg-rose-950/60 border border-rose-500/30 text-rose-300 font-mono"
                            >
                              {ci.citation_id}: {ci.issue_type}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 max-w-sm text-slate-400 italic">
                      {item.corrected_answer ? `"${item.corrected_answer}"` : "None"}
                    </td>
                    <td className="px-6 py-4">
                      <Badge
                        variant={
                          item.triage_status === "PROMOTED_TO_GOLDEN"
                            ? "success"
                            : item.triage_status === "TRIAGED"
                            ? "neutral"
                            : "outline"
                        }
                      >
                        {item.triage_status}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 text-right space-x-2">
                      {item.triage_status !== "PROMOTED_TO_GOLDEN" && (
                        <button
                          onClick={() => handlePromote(item.id)}
                          disabled={actionLoading === item.id}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-sky-500/20 hover:bg-sky-500/30 border border-sky-500/40 text-sky-300 text-[11px] font-semibold transition"
                        >
                          <Sparkles className="w-3 h-3 text-sky-400" />
                          <span>1-Click Golden</span>
                        </button>
                      )}
                      {item.triage_status === "NEW" && (
                        <button
                          onClick={() => handleTriage(item.id, "TRIAGED")}
                          disabled={actionLoading === item.id}
                          className="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] font-medium transition"
                        >
                          Mark Triaged
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
