"use client";

import React from "react";
import { Clock, CheckCircle2, AlertTriangle, RefreshCw, Database } from "lucide-react";

export interface SyncLogEntry {
  id: string;
  connectorName: string;
  startedAt: string;
  durationSeconds: number;
  docsSynchronized: number;
  status: "SUCCESS" | "SYNCING" | "FAILED";
  errorDetails?: string;
}

export function SyncLogTable() {
  const sampleLogs: SyncLogEntry[] = [
    {
      id: "sync-log-01",
      connectorName: "Google Drive (Enterprise)",
      startedAt: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
      durationSeconds: 4.2,
      docsSynchronized: 6,
      status: "SUCCESS",
    },
    {
      id: "sync-log-02",
      connectorName: "Atlassian Confluence",
      startedAt: new Date(Date.now() - 75 * 60 * 1000).toISOString(),
      durationSeconds: 12.8,
      docsSynchronized: 28,
      status: "SUCCESS",
    },
    {
      id: "sync-log-03",
      connectorName: "Microsoft SharePoint",
      startedAt: new Date(Date.now() - 4 * 3600 * 1000).toISOString(),
      durationSeconds: 1.5,
      docsSynchronized: 0,
      status: "FAILED",
      errorDetails: "Graph API token expired: re-authentication required",
    },
  ];

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-xl shadow-xl space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <Database className="w-4 h-4 text-sky-400" />
          <span>Connector Synchronization & Ingestion Audit Log</span>
        </h3>
        <span className="text-[11px] font-mono text-slate-500">Last 24 Hours</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-slate-950/60 text-[10px] uppercase font-mono text-slate-500 border-b border-slate-800">
            <tr>
              <th className="py-2.5 px-3">Connector</th>
              <th className="py-2.5 px-3">Status</th>
              <th className="py-2.5 px-3">Documents Synced</th>
              <th className="py-2.5 px-3">Duration</th>
              <th className="py-2.5 px-3">Timestamp</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {sampleLogs.map((log) => (
              <tr key={log.id} className="hover:bg-slate-850/40 transition-colors">
                <td className="py-3 px-3 font-semibold text-slate-200">
                  <div>{log.connectorName}</div>
                  {log.errorDetails && (
                    <div className="text-[10px] text-rose-400 font-mono mt-0.5">{log.errorDetails}</div>
                  )}
                </td>
                <td className="py-3 px-3">
                  <span
                    className={`inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-full ${
                      log.status === "SUCCESS"
                        ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                        : log.status === "SYNCING"
                        ? "bg-sky-500/10 text-sky-400 border border-sky-500/20"
                        : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                    }`}
                  >
                    {log.status === "SUCCESS" && <CheckCircle2 className="w-3 h-3" />}
                    {log.status === "SYNCING" && <RefreshCw className="w-3 h-3 animate-spin" />}
                    {log.status === "FAILED" && <AlertTriangle className="w-3 h-3" />}
                    {log.status}
                  </span>
                </td>
                <td className="py-3 px-3 font-mono text-slate-300">{log.docsSynchronized} docs</td>
                <td className="py-3 px-3 font-mono text-slate-400">{log.durationSeconds}s</td>
                <td className="py-3 px-3 font-mono text-slate-500 text-[11px]">
                  {new Date(log.startedAt).toLocaleTimeString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
