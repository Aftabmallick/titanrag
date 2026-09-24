"use client";

import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  Users,
  Activity,
  Zap,
  Server,
  CheckCircle,
  XCircle,
  Layers,
} from "lucide-react";

interface SystemStats {
  total_tenants: number;
  active_subscriptions: number;
  total_queries_today: number;
  total_documents_indexed: number;
  vector_count: number;
  worker_queue_depths: Record<string, number>;
  p99_latency_ms: number;
  error_rate_percent: number;
  service_health: Record<string, string>;
}

function StatCard({
  icon,
  label,
  value,
  sub,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  sub?: string;
  accent?: string;
}) {
  return (
    <div className="glass-card rounded-2xl border border-slate-700/50 p-5">
      <div className="flex items-center justify-between mb-3">
        <span className={`w-9 h-9 flex items-center justify-center rounded-xl ${accent || "bg-slate-700/60"}`}>
          {icon}
        </span>
        {sub && (
          <span className="text-xs text-slate-500 font-medium">{sub}</span>
        )}
      </div>
      <p className="text-2xl font-bold text-slate-100">
        {typeof value === "number" ? value.toLocaleString() : value}
      </p>
      <p className="text-xs text-slate-500 mt-1">{label}</p>
    </div>
  );
}

function ServiceHealthBadge({ service, status }: { service: string; status: string }) {
  const healthy = status === "healthy";
  return (
    <div className="flex items-center justify-between py-2.5 px-4 rounded-xl border border-slate-700/50 bg-slate-800/30">
      <div className="flex items-center gap-2.5">
        <Server className="w-3.5 h-3.5 text-slate-500" />
        <span className="text-sm text-slate-300 capitalize">{service}</span>
      </div>
      <div className="flex items-center gap-1.5">
        {healthy ? (
          <>
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <CheckCircle className="w-4 h-4 text-emerald-400" />
          </>
        ) : (
          <>
            <div className="w-2 h-2 rounded-full bg-red-500" />
            <XCircle className="w-4 h-4 text-red-400" />
          </>
        )}
      </div>
    </div>
  );
}

function QueueDepthBar({
  queue,
  depth,
}: {
  queue: string;
  depth: number;
}) {
  const max = 1000;
  const pct = Math.min((depth / max) * 100, 100);
  const color =
    pct > 80 ? "bg-red-500" : pct > 50 ? "bg-amber-500" : "bg-emerald-500";

  const queueLabels: Record<string, string> = {
    p1_default: "P1 Default",
    p2_bulk_sync: "P2 Bulk Sync",
    p3_heavy_gpu: "P3 GPU",
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-1">
        <span className="text-xs text-slate-400">{queueLabels[queue] || queue}</span>
        <span
          className={`text-xs font-semibold ${
            pct > 80 ? "text-red-400" : pct > 50 ? "text-amber-400" : "text-emerald-400"
          }`}
        >
          {depth.toLocaleString()} tasks
        </span>
      </div>
      <div className="h-2 bg-slate-700/60 rounded-full overflow-hidden">
        <div
          className={`h-full ${color} rounded-full transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function SystemHealthCard() {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  async function fetchStats() {
    const token = localStorage.getItem("titan_token") || "";
    try {
      const res = await fetch("/api/v1/platform/stats", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setStats(await res.json());
        setLastUpdated(new Date());
      }
    } catch {
      // silent fail
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchStats();
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchStats, 30_000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-24 bg-slate-800/40 rounded-2xl animate-pulse" />
        ))}
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="flex items-center gap-2 text-red-400 text-sm p-4">
        <AlertTriangle className="w-4 h-4" />
        Failed to load system stats
      </div>
    );
  }

  const allHealthy = Object.values(stats.service_health).every((s) => s === "healthy");

  return (
    <div className="space-y-6">
      {/* Overall status banner */}
      <div
        className={`flex items-center gap-3 px-4 py-3 rounded-xl border text-sm font-medium ${
          allHealthy
            ? "bg-emerald-950/30 border-emerald-800/40 text-emerald-300"
            : "bg-red-950/30 border-red-800/40 text-red-300"
        }`}
        role="status"
        aria-label={allHealthy ? "All systems operational" : "System degradation detected"}
      >
        {allHealthy ? (
          <CheckCircle className="w-5 h-5" />
        ) : (
          <AlertTriangle className="w-5 h-5" />
        )}
        {allHealthy ? "All systems operational" : "System degradation detected"}
        {lastUpdated && (
          <span className="ml-auto text-xs opacity-60">
            Updated {lastUpdated.toLocaleTimeString()}
          </span>
        )}
      </div>

      {/* Key metrics grid */}
      <div className="grid grid-cols-2 gap-4">
        <StatCard
          icon={<Users className="w-4 h-4 text-indigo-400" />}
          label="Active Tenants"
          value={stats.total_tenants}
          accent="bg-indigo-900/40"
        />
        <StatCard
          icon={<Activity className="w-4 h-4 text-emerald-400" />}
          label="Queries Today"
          value={stats.total_queries_today}
          accent="bg-emerald-900/40"
        />
        <StatCard
          icon={<Zap className="w-4 h-4 text-amber-400" />}
          label="P99 Latency"
          value={`${stats.p99_latency_ms.toFixed(0)}ms`}
          sub={stats.p99_latency_ms > 500 ? "⚠ High" : "Good"}
          accent="bg-amber-900/40"
        />
        <StatCard
          icon={<Layers className="w-4 h-4 text-violet-400" />}
          label="Vectors Indexed"
          value={stats.vector_count}
          accent="bg-violet-900/40"
        />
      </div>

      {/* Worker queue depths */}
      <div className="glass-card rounded-2xl border border-slate-700/50 p-5 space-y-3">
        <h4 className="text-sm font-semibold text-slate-300">Worker Queue Depths</h4>
        {Object.entries(stats.worker_queue_depths).map(([q, d]) => (
          <QueueDepthBar key={q} queue={q} depth={d} />
        ))}
      </div>

      {/* Service health */}
      <div className="glass-card rounded-2xl border border-slate-700/50 p-5 space-y-2">
        <h4 className="text-sm font-semibold text-slate-300 mb-3">Service Health</h4>
        {Object.entries(stats.service_health).map(([service, status]) => (
          <ServiceHealthBadge key={service} service={service} status={status} />
        ))}
      </div>
    </div>
  );
}
