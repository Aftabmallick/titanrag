"use client";

import React, { useState } from "react";
import {
  Search,
  Filter,
  Download,
  ChevronDown,
  ChevronRight,
  Shield,
  Clock,
  User as UserIcon,
} from "lucide-react";

export interface AuditLogEntry {
  id: string;
  tenant_id: string;
  user_email: string;
  action: string;
  resource_type: string;
  resource_id: string;
  ip_address: string;
  status: "SUCCESS" | "FAILED" | "DENIED";
  created_at: string;
  details: Record<string, any>;
}

interface GlobalAuditTableProps {
  entries: AuditLogEntry[];
  onExportCSV: () => void;
  selectedTenantId?: string;
}

export function GlobalAuditTable({
  entries,
  onExportCSV,
  selectedTenantId,
}: GlobalAuditTableProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [actionFilter, setActionFilter] = useState("ALL");
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const filtered = entries.filter((entry) => {
    const matchesSearch =
      entry.user_email.toLowerCase().includes(searchTerm.toLowerCase()) ||
      entry.tenant_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      entry.action.toLowerCase().includes(searchTerm.toLowerCase()) ||
      entry.resource_type.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesAction = actionFilter === "ALL" || entry.action === actionFilter;
    const matchesTenant = !selectedTenantId || entry.tenant_id === selectedTenantId;

    return matchesSearch && matchesAction && matchesTenant;
  });

  const getStatusBadge = (status: AuditLogEntry["status"]) => {
    switch (status) {
      case "SUCCESS":
        return "bg-emerald-950/60 text-emerald-300 border-emerald-800/60";
      case "FAILED":
        return "bg-rose-950/60 text-rose-300 border-rose-800/60";
      case "DENIED":
        return "bg-amber-950/60 text-amber-300 border-amber-800/60";
    }
  };

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative w-full sm:w-96">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search email, tenant ID, action..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-slate-900 border border-slate-800 rounded-lg text-sm text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            aria-label="Filter audit logs"
          />
        </div>

        <div className="flex items-center gap-2 self-end sm:self-auto">
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="bg-slate-900 border border-slate-800 rounded-lg text-sm text-slate-200 py-1.5 px-3 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            aria-label="Filter by action"
          >
            <option value="ALL">All Actions</option>
            <option value="auth.login">auth.login</option>
            <option value="document.upload">document.upload</option>
            <option value="document.delete">document.delete</option>
            <option value="api_key.create">api_key.create</option>
            <option value="quota.update">quota.update</option>
          </select>

          <button
            onClick={onExportCSV}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 rounded-lg text-sm font-medium transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            Export CSV
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-slate-800/80 bg-slate-950/60 shadow-xl backdrop-blur-md">
        <table className="w-full text-left text-sm" role="table">
          <thead className="bg-slate-900/70 border-b border-slate-800 text-xs font-semibold uppercase text-slate-400">
            <tr>
              <th scope="col" className="w-8 px-4 py-3"></th>
              <th scope="col" className="px-6 py-3">Timestamp</th>
              <th scope="col" className="px-6 py-3">Tenant / Actor</th>
              <th scope="col" className="px-6 py-3">Action</th>
              <th scope="col" className="px-6 py-3">Resource</th>
              <th scope="col" className="px-6 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-12 text-center text-slate-400">
                  No audit logs found.
                </td>
              </tr>
            ) : (
              filtered.map((log) => {
                const isExpanded = expandedRow === log.id;
                return (
                  <React.Fragment key={log.id}>
                    <tr
                      onClick={() => setExpandedRow(isExpanded ? null : log.id)}
                      className="cursor-pointer hover:bg-slate-900/40 transition-colors"
                    >
                      <td className="px-4 py-3 text-slate-400">
                        {isExpanded ? (
                          <ChevronDown className="w-4 h-4" />
                        ) : (
                          <ChevronRight className="w-4 h-4" />
                        )}
                      </td>
                      <td className="px-6 py-3 text-xs text-slate-400 whitespace-nowrap">
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                      <td className="px-6 py-3">
                        <div className="font-medium text-slate-200">{log.user_email}</div>
                        <div className="text-xs text-slate-500 font-mono">{log.tenant_id}</div>
                      </td>
                      <td className="px-6 py-3">
                        <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-indigo-300">
                          {log.action}
                        </span>
                      </td>
                      <td className="px-6 py-3 text-xs text-slate-300">
                        <div>{log.resource_type}</div>
                        <div className="text-slate-500 font-mono">{log.resource_id}</div>
                      </td>
                      <td className="px-6 py-3">
                        <span
                          className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getStatusBadge(
                            log.status
                          )}`}
                        >
                          {log.status}
                        </span>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr className="bg-slate-900/60 border-t border-slate-800/80">
                        <td colSpan={6} className="px-8 py-4">
                          <div className="space-y-2">
                            <div className="text-xs font-semibold text-slate-300 flex items-center gap-2">
                              <span>IP: {log.ip_address}</span>
                              <span>&bull;</span>
                              <span>ID: {log.id}</span>
                            </div>
                            <pre className="p-3 bg-slate-950 rounded-lg border border-slate-800 font-mono text-xs text-slate-300 overflow-x-auto">
                              {JSON.stringify(log.details, null, 2)}
                            </pre>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
