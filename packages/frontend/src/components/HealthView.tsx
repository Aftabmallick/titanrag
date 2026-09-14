"use client";

import React, { useState, useEffect } from "react";
import { Server, Database, CheckCircle2, AlertTriangle, RefreshCw, Cpu, Activity } from "lucide-react";
import { api, HealthStatus } from "@/lib/api";

export function HealthView() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchHealth = async () => {
    try {
      setLoading(true);
      const res = await api.getHealthReady();
      setHealth(res);
    } catch (err: any) {
      console.warn("Health query failed:", err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  const deps = health?.dependencies;

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-xl shadow-2xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <Activity className="w-5 h-5 text-emerald-400" />
            Infrastructure & Dependency Readiness
          </h2>
          <p className="text-sm text-slate-400">
            Real-time ping and latency metrics across core backing services and vector engines
          </p>
        </div>

        <button
          onClick={fetchHealth}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-950/80 hover:bg-slate-800 text-xs text-slate-300 transition-colors cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* PostgreSQL */}
        <div className="p-5 rounded-xl border border-slate-800 bg-slate-950/60 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">PostgreSQL 16</span>
            <Database className="w-4 h-4 text-sky-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-black text-white capitalize">
              {deps?.postgres?.status || "Unknown"}
            </span>
            {deps?.postgres?.latency_ms !== undefined && (
              <span className="text-xs font-mono text-emerald-400">{deps.postgres.latency_ms} ms</span>
            )}
          </div>
          <p className="text-xs text-slate-500">Row-Level Security + Outbox Log</p>
        </div>

        {/* Redis */}
        <div className="p-5 rounded-xl border border-slate-800 bg-slate-950/60 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Redis 7</span>
            <Cpu className="w-4 h-4 text-rose-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-black text-white capitalize">
              {deps?.redis?.status || "Unknown"}
            </span>
            {deps?.redis?.latency_ms !== undefined && (
              <span className="text-xs font-mono text-emerald-400">{deps.redis.latency_ms} ms</span>
            )}
          </div>
          <p className="text-xs text-slate-500">Celery Broker & Rate Limiting</p>
        </div>

        {/* Qdrant */}
        <div className="p-5 rounded-xl border border-slate-800 bg-slate-950/60 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Qdrant 1.12</span>
            <Server className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-black text-white capitalize">
              {deps?.qdrant?.status || "Unknown"}
            </span>
            {deps?.qdrant?.latency_ms !== undefined && (
              <span className="text-xs font-mono text-emerald-400">{deps.qdrant.latency_ms} ms</span>
            )}
          </div>
          <p className="text-xs text-slate-500">Dual-Vector HNSW + BM25</p>
        </div>

        {/* MinIO */}
        <div className="p-5 rounded-xl border border-slate-800 bg-slate-950/60 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">MinIO S3</span>
            <Server className="w-4 h-4 text-amber-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-black text-white capitalize">
              {deps?.minio?.status || "Local Fallback"}
            </span>
            {deps?.minio?.latency_ms !== undefined && (
              <span className="text-xs font-mono text-slate-400">{deps.minio.latency_ms} ms</span>
            )}
          </div>
          <p className="text-xs text-slate-500">Raw Document Storage Engine</p>
        </div>
      </div>
    </div>
  );
}
