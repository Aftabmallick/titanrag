"use client";

import React, { useState } from "react";
import {
  Search,
  MoreVertical,
  ShieldAlert,
  ShieldCheck,
  HardDrive,
  Cpu,
  ExternalLink,
  ChevronDown,
  Filter,
} from "lucide-react";

export interface TenantRow {
  id: string;
  name: string;
  plan: "FREE" | "PRO" | "ENTERPRISE" | "SANDBOX";
  status: "ACTIVE" | "SUSPENDED" | "READ_ONLY";
  cu_consumed: number;
  cu_limit: number;
  storage_bytes: number;
  storage_limit_bytes: number;
  user_count: number;
  created_at: string;
}

interface TenantTableProps {
  tenants: TenantRow[];
  onSuspend: (tenantId: string) => Promise<void>;
  onUnsuspend: (tenantId: string) => Promise<void>;
  onEditQuota: (tenant: TenantRow) => void;
  onViewAudit: (tenantId: string) => void;
}

export function TenantTable({
  tenants,
  onSuspend,
  onUnsuspend,
  onEditQuota,
  onViewAudit,
}: TenantTableProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [planFilter, setPlanFilter] = useState<string>("ALL");
  const [actionMenuOpen, setActionMenuOpen] = useState<string | null>(null);

  const filtered = tenants.filter((t) => {
    const matchesSearch =
      t.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.id.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesPlan = planFilter === "ALL" || t.plan === planFilter;
    return matchesSearch && matchesPlan;
  });

  const formatStorage = (bytes: number) => {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  };

  const getPlanBadgeStyle = (plan: TenantRow["plan"]) => {
    switch (plan) {
      case "ENTERPRISE":
        return "bg-purple-900/40 text-purple-300 border-purple-700/50";
      case "PRO":
        return "bg-indigo-900/40 text-indigo-300 border-indigo-700/50";
      case "FREE":
        return "bg-slate-800 text-slate-300 border-slate-700";
      case "SANDBOX":
        return "bg-amber-900/40 text-amber-300 border-amber-700/50";
    }
  };

  const getStatusBadgeStyle = (status: TenantRow["status"]) => {
    switch (status) {
      case "ACTIVE":
        return "bg-emerald-900/40 text-emerald-300 border-emerald-700/50";
      case "READ_ONLY":
        return "bg-amber-900/40 text-amber-300 border-amber-700/50";
      case "SUSPENDED":
        return "bg-rose-900/40 text-rose-300 border-rose-700/50";
    }
  };

  return (
    <div className="space-y-4">
      {/* Controls Bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="relative w-full sm:w-80">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search tenant name or ID..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-slate-900/80 border border-slate-800 rounded-lg text-sm text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            aria-label="Filter tenants"
          />
        </div>

        <div className="flex items-center gap-2 self-end sm:self-auto">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={planFilter}
            onChange={(e) => setPlanFilter(e.target.value)}
            className="bg-slate-900 border border-slate-800 rounded-lg text-sm text-slate-200 py-1.5 px-3 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            aria-label="Filter by plan"
          >
            <option value="ALL">All Plans</option>
            <option value="ENTERPRISE">Enterprise</option>
            <option value="PRO">Pro</option>
            <option value="FREE">Free</option>
            <option value="SANDBOX">Sandbox</option>
          </select>
        </div>
      </div>

      {/* Table Container */}
      <div className="overflow-x-auto rounded-xl border border-slate-800/80 bg-slate-950/60 shadow-xl backdrop-blur-md">
        <table className="w-full text-left text-sm" role="table">
          <thead className="bg-slate-900/70 border-b border-slate-800 text-xs font-semibold uppercase text-slate-400">
            <tr>
              <th scope="col" className="px-6 py-4">Tenant</th>
              <th scope="col" className="px-6 py-4">Plan & Status</th>
              <th scope="col" className="px-6 py-4">Compute Units (CU)</th>
              <th scope="col" className="px-6 py-4">Storage</th>
              <th scope="col" className="px-6 py-4">Users</th>
              <th scope="col" className="px-6 py-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-12 text-center text-slate-400">
                  No tenants match the criteria.
                </td>
              </tr>
            ) : (
              filtered.map((tenant) => {
                const cuPercent = Math.min(
                  100,
                  Math.round((tenant.cu_consumed / Math.max(1, tenant.cu_limit)) * 100)
                );
                const storagePercent = Math.min(
                  100,
                  Math.round(
                    (tenant.storage_bytes / Math.max(1, tenant.storage_limit_bytes)) * 100
                  )
                );

                return (
                  <tr
                    key={tenant.id}
                    className="hover:bg-slate-900/40 transition-colors duration-150"
                  >
                    <td className="px-6 py-4 font-medium text-slate-100">
                      <div>{tenant.name}</div>
                      <div className="text-xs text-slate-500 font-mono">{tenant.id}</div>
                    </td>

                    <td className="px-6 py-4">
                      <div className="flex flex-col gap-1.5 items-start">
                        <span
                          className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium border ${getPlanBadgeStyle(
                            tenant.plan
                          )}`}
                        >
                          {tenant.plan}
                        </span>
                        <span
                          className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium border ${getStatusBadgeStyle(
                            tenant.status
                          )}`}
                        >
                          {tenant.status}
                        </span>
                      </div>
                    </td>

                    <td className="px-6 py-4 min-w-[180px]">
                      <div className="flex items-center justify-between text-xs text-slate-300 mb-1">
                        <span className="flex items-center gap-1">
                          <Cpu className="w-3 h-3 text-indigo-400" />
                          {tenant.cu_consumed.toLocaleString()} / {tenant.cu_limit.toLocaleString()}
                        </span>
                        <span className={cuPercent > 90 ? "text-rose-400 font-semibold" : ""}>
                          {cuPercent}%
                        </span>
                      </div>
                      <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            cuPercent > 90
                              ? "bg-rose-500"
                              : cuPercent > 75
                              ? "bg-amber-500"
                              : "bg-indigo-500"
                          }`}
                          style={{ width: `${cuPercent}%` }}
                        />
                      </div>
                    </td>

                    <td className="px-6 py-4 min-w-[160px]">
                      <div className="flex items-center justify-between text-xs text-slate-300 mb-1">
                        <span className="flex items-center gap-1">
                          <HardDrive className="w-3 h-3 text-slate-400" />
                          {formatStorage(tenant.storage_bytes)}
                        </span>
                        <span>{storagePercent}%</span>
                      </div>
                      <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-slate-400 rounded-full"
                          style={{ width: `${storagePercent}%` }}
                        />
                      </div>
                    </td>

                    <td className="px-6 py-4 text-slate-300">
                      {tenant.user_count}
                    </td>

                    <td className="px-6 py-4 text-right">
                      <div className="relative inline-block text-left">
                        <button
                          onClick={() =>
                            setActionMenuOpen(actionMenuOpen === tenant.id ? null : tenant.id)
                          }
                          className="p-1.5 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-slate-100 transition-colors"
                          aria-label={`Actions for ${tenant.name}`}
                        >
                          <MoreVertical className="w-4 h-4" />
                        </button>

                        {actionMenuOpen === tenant.id && (
                          <div
                            className="absolute right-0 mt-2 w-48 bg-slate-900 border border-slate-700/80 rounded-lg shadow-2xl py-1 z-20"
                            role="menu"
                          >
                            <button
                              onClick={() => {
                                onEditQuota(tenant);
                                setActionMenuOpen(null);
                              }}
                              className="w-full text-left px-4 py-2 text-xs text-slate-200 hover:bg-slate-800"
                              role="menuitem"
                            >
                              Manage Quota
                            </button>
                            <button
                              onClick={() => {
                                onViewAudit(tenant.id);
                                setActionMenuOpen(null);
                              }}
                              className="w-full text-left px-4 py-2 text-xs text-slate-200 hover:bg-slate-800 flex items-center justify-between"
                              role="menuitem"
                            >
                              <span>View Audit Log</span>
                              <ExternalLink className="w-3 h-3" />
                            </button>
                            <div className="my-1 border-t border-slate-800" />
                            {tenant.status === "ACTIVE" ? (
                              <button
                                onClick={() => {
                                  onSuspend(tenant.id);
                                  setActionMenuOpen(null);
                                }}
                                className="w-full text-left px-4 py-2 text-xs text-rose-400 hover:bg-rose-950/40 flex items-center gap-1.5"
                                role="menuitem"
                              >
                                <ShieldAlert className="w-3.5 h-3.5" />
                                Suspend Tenant
                              </button>
                            ) : (
                              <button
                                onClick={() => {
                                  onUnsuspend(tenant.id);
                                  setActionMenuOpen(null);
                                }}
                                className="w-full text-left px-4 py-2 text-xs text-emerald-400 hover:bg-emerald-950/40 flex items-center gap-1.5"
                                role="menuitem"
                              >
                                <ShieldCheck className="w-3.5 h-3.5" />
                                Activate Tenant
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
