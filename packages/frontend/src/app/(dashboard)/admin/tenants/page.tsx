"use client";

import React, { useState } from "react";
import { Building2, Users, AlertCircle, RefreshCw } from "lucide-react";
import { TenantTable, TenantRow } from "@/components/admin/TenantTable";

const INITIAL_TENANTS: TenantRow[] = [
  {
    id: "tenant-acme-corp",
    name: "Acme Corporation",
    plan: "ENTERPRISE",
    status: "ACTIVE",
    cu_consumed: 68420,
    cu_limit: 100000,
    storage_bytes: 42 * 1024 * 1024 * 1024,
    storage_limit_bytes: 100 * 1024 * 1024 * 1024,
    user_count: 142,
    created_at: "2026-01-15T08:00:00Z",
  },
  {
    id: "tenant-startup-ai",
    name: "HyperScale AI",
    plan: "PRO",
    status: "ACTIVE",
    cu_consumed: 4890,
    cu_limit: 5000,
    storage_bytes: 8.5 * 1024 * 1024 * 1024,
    storage_limit_bytes: 10 * 1024 * 1024 * 1024,
    user_count: 18,
    created_at: "2026-03-01T12:00:00Z",
  },
  {
    id: "tenant-dev-lab",
    name: "DevLab Research",
    plan: "FREE",
    status: "READ_ONLY",
    cu_consumed: 100,
    cu_limit: 100,
    storage_bytes: 480 * 1024 * 1024,
    storage_limit_bytes: 500 * 1024 * 1024,
    user_count: 3,
    created_at: "2026-04-10T15:30:00Z",
  },
  {
    id: "tenant-demo-sandbox",
    name: "Sandbox Session #891",
    plan: "SANDBOX",
    status: "ACTIVE",
    cu_consumed: 4,
    cu_limit: 10,
    storage_bytes: 12 * 1024 * 1024,
    storage_limit_bytes: 50 * 1024 * 1024,
    user_count: 1,
    created_at: "2026-09-24T10:00:00Z",
  },
];

export default function TenantsAdminPage() {
  const [tenants, setTenants] = useState<TenantRow[]>(INITIAL_TENANTS);
  const [selectedTenant, setSelectedTenant] = useState<TenantRow | null>(null);
  const [editQuotaModalOpen, setEditQuotaModalOpen] = useState(false);
  const [newCuLimit, setNewCuLimit] = useState<number>(0);

  const handleSuspend = async (tenantId: string) => {
    setTenants((prev) =>
      prev.map((t) => (t.id === tenantId ? { ...t, status: "SUSPENDED" } : t))
    );
  };

  const handleUnsuspend = async (tenantId: string) => {
    setTenants((prev) =>
      prev.map((t) => (t.id === tenantId ? { ...t, status: "ACTIVE" } : t))
    );
  };

  const handleEditQuota = (tenant: TenantRow) => {
    setSelectedTenant(tenant);
    setNewCuLimit(tenant.cu_limit);
    setEditQuotaModalOpen(true);
  };

  const saveQuota = () => {
    if (selectedTenant) {
      setTenants((prev) =>
        prev.map((t) =>
          t.id === selectedTenant.id ? { ...t, cu_limit: newCuLimit } : t
        )
      );
      setEditQuotaModalOpen(false);
    }
  };

  return (
    <div className="space-y-8 p-6 lg:p-10 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2.5">
            <Building2 className="w-7 h-7 text-indigo-400" />
            Tenant Management
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Super-admin overview of all active tenants, subscription plans, and resource consumption.
          </p>
        </div>
      </div>

      {/* Main Tenant Table */}
      <TenantTable
        tenants={tenants}
        onSuspend={handleSuspend}
        onUnsuspend={handleUnsuspend}
        onEditQuota={handleEditQuota}
        onViewAudit={(id) => {
          window.location.href = `/admin/audit?tenant_id=${id}`;
        }}
      />

      {/* Quota Modal */}
      {editQuotaModalOpen && selectedTenant && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <h3 className="text-lg font-semibold text-slate-100">
              Update Quota for {selectedTenant.name}
            </h3>
            <p className="text-xs text-slate-400">
              Configure custom monthly Compute Unit (CU) ceiling. Overriding the plan limit will adjust gatekeeper enforcement immediately.
            </p>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                Monthly CU Limit
              </label>
              <input
                type="number"
                value={newCuLimit}
                onChange={(e) => setNewCuLimit(parseInt(e.target.value) || 0)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setEditQuotaModalOpen(false)}
                className="px-4 py-2 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200"
              >
                Cancel
              </button>
              <button
                onClick={saveQuota}
                className="px-4 py-2 rounded-lg text-xs font-medium bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/30"
              >
                Save Quota
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
