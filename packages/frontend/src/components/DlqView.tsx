"use client";

import React, { useState, useEffect } from "react";
import { AlertOctagon, RefreshCw, CheckCircle2, ShieldAlert, Clock, Loader2 } from "lucide-react";
import { api, DLQTaskRecord } from "@/lib/api";

export function DlqView() {
  const [tasks, setTasks] = useState<DLQTaskRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [retryingId, setRetryingId] = useState<string | null>(null);

  const fetchDLQ = async () => {
    try {
      setLoading(true);
      const res = await api.listDLQTasks();
      setTasks(res.items);
    } catch (err: any) {
      console.warn("Could not fetch DLQ:", err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDLQ();
  }, []);

  const handleRetry = async (taskId: string) => {
    setRetryingId(taskId);
    try {
      await api.retryDLQTask(taskId);
      await fetchDLQ();
    } catch (err: any) {
      alert("Failed to retry DLQ task: " + err.message);
    } finally {
      setRetryingId(null);
    }
  };

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-xl shadow-2xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <AlertOctagon className="w-5 h-5 text-rose-400" />
            Dead Letter Queue (DLQ)
          </h2>
          <p className="text-sm text-slate-400">
            Ingestion failures captured after 3 exponential Celery backoff attempts with transactional outbox rollback
          </p>
        </div>

        <button
          onClick={fetchDLQ}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-950/80 hover:bg-slate-800 text-xs text-slate-300 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh</span>
        </button>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/50">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-slate-900/80 text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800">
            <tr>
              <th className="py-3 px-4 font-semibold">Task ID</th>
              <th className="py-3 px-4 font-semibold">Type</th>
              <th className="py-3 px-4 font-semibold">Error Trace</th>
              <th className="py-3 px-4 font-semibold">Retries</th>
              <th className="py-3 px-4 font-semibold">Failed At</th>
              <th className="py-3 px-4 font-semibold text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {loading ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-slate-500">
                  Checking DLQ...
                </td>
              </tr>
            ) : tasks.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-emerald-400">
                  <div className="flex items-center justify-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span>DLQ is empty. All background worker tasks are executing cleanly.</span>
                  </div>
                </td>
              </tr>
            ) : (
              tasks.map((t) => (
                <tr key={t.id} className="hover:bg-slate-900/40 transition-colors">
                  <td className="py-3 px-4 font-mono text-slate-300">{t.id}</td>
                  <td className="py-3 px-4 font-mono text-slate-400">{t.task_type}</td>
                  <td className="py-3 px-4 max-w-xs truncate text-rose-400 font-mono text-[11px]">
                    {t.error_message || "Unknown error"}
                  </td>
                  <td className="py-3 px-4 font-mono">{t.retry_count} / 3</td>
                  <td className="py-3 px-4 font-mono text-slate-400">
                    {new Date(t.updated_at).toLocaleTimeString()}
                  </td>
                  <td className="py-3 px-4 text-right">
                    <button
                      onClick={() => handleRetry(t.id)}
                      disabled={retryingId === t.id}
                      className="flex items-center gap-1.5 ml-auto px-3 py-1 rounded-lg bg-sky-500/10 hover:bg-sky-500/20 text-sky-400 border border-sky-500/30 text-xs font-semibold transition-colors disabled:opacity-50"
                    >
                      {retryingId === t.id ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <RefreshCw className="w-3 h-3" />
                      )}
                      <span>Retry Pipeline</span>
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
