"use client";

import React from "react";
import { Activity, Server, Cpu, Database, Network } from "lucide-react";
import { SystemHealthCard } from "@/components/admin/SystemHealthCard";

export default function SystemHealthAdminPage() {
  return (
    <div className="space-y-8 p-6 lg:p-10 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2.5">
          <Activity className="w-7 h-7 text-indigo-400" />
          System Health & Infrastructure
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Real-time health monitoring of API microservices, Celery worker task queues, vector indexes, and caches.
        </p>
      </div>

      {/* Main System Health Monitor */}
      <SystemHealthCard />

      {/* Infrastructure Details Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="p-6 rounded-xl border border-slate-800 bg-slate-950/60 shadow-xl space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-200">
            <Database className="w-4 h-4 text-purple-400" />
            Top Qdrant Vector Collections
          </div>
          <div className="space-y-3">
            {[
              { name: "workspace_enterprise_docs", points: "1,248,000", dim: 1536, ram: "4.8 GB" },
              { name: "colpali_multimodal_store", points: "450,200", dim: 128, ram: "2.1 GB" },
              { name: "legal_contracts_hybrid", points: "210,000", dim: 1536, ram: "1.2 GB" },
              { name: "sandbox_demo_projections", points: "12,500", dim: 1536, ram: "84 MB" },
            ].map((col) => (
              <div
                key={col.name}
                className="flex items-center justify-between p-3 rounded-lg bg-slate-900/60 border border-slate-800/80 text-xs"
              >
                <div>
                  <div className="font-medium text-slate-200">{col.name}</div>
                  <div className="text-slate-500 font-mono">Dim: {col.dim}</div>
                </div>
                <div className="text-right">
                  <div className="font-semibold text-slate-300">{col.points} points</div>
                  <div className="text-slate-500">{col.ram}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="p-6 rounded-xl border border-slate-800 bg-slate-950/60 shadow-xl space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-200">
            <Network className="w-4 h-4 text-emerald-400" />
            Active Microservices & Endpoints
          </div>
          <div className="space-y-3">
            {[
              { service: "titan-api (FastAPI)", port: ":8000", uptime: "99.98%", status: "HEALTHY" },
              { service: "titan-workers-core (Celery)", port: "Internal", uptime: "99.95%", status: "HEALTHY" },
              { service: "titan-workers-heavy (GPU/ColPali)", port: "Internal", uptime: "100%", status: "HEALTHY" },
              { service: "titanrag-sandbox (Isolated Pod)", port: ":8001", uptime: "99.90%", status: "HEALTHY" },
            ].map((srv) => (
              <div
                key={srv.service}
                className="flex items-center justify-between p-3 rounded-lg bg-slate-900/60 border border-slate-800/80 text-xs"
              >
                <div>
                  <div className="font-medium text-slate-200">{srv.service}</div>
                  <div className="text-slate-500 font-mono">Port: {srv.port}</div>
                </div>
                <div className="text-right">
                  <div className="font-semibold text-emerald-400">{srv.status}</div>
                  <div className="text-slate-500">{srv.uptime}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
