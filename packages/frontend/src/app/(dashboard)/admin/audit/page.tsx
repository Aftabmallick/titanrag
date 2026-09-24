"use client";

import React, { useState } from "react";
import { ShieldCheck, Download, History } from "lucide-react";
import { GlobalAuditTable, AuditLogEntry } from "@/components/admin/GlobalAuditTable";

const MOCK_AUDIT_LOGS: AuditLogEntry[] = [
  {
    id: "aud-001",
    tenant_id: "tenant-acme-corp",
    user_email: "secops@acme.corp",
    action: "auth.login",
    resource_type: "session",
    resource_id: "sess_9182",
    ip_address: "198.51.100.24",
    status: "SUCCESS",
    created_at: "2026-09-24T16:30:00Z",
    details: {
      auth_method: "SAML_SSO",
      mfa_verified: true,
      user_agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    },
  },
  {
    id: "aud-002",
    tenant_id: "tenant-startup-ai",
    user_email: "founder@hyperscale.ai",
    action: "quota.update",
    resource_type: "tenant_quota",
    resource_id: "quota_cu_limit",
    ip_address: "203.0.113.88",
    status: "SUCCESS",
    created_at: "2026-09-24T15:10:00Z",
    details: {
      previous_limit: 5000,
      new_limit: 10000,
      reason: "Platform Admin Manual Quota Boost",
    },
  },
  {
    id: "aud-003",
    tenant_id: "tenant-dev-lab",
    user_email: "dev@research.org",
    action: "document.upload",
    resource_type: "document",
    resource_id: "doc_patent_2026",
    ip_address: "192.0.2.14",
    status: "DENIED",
    created_at: "2026-09-24T14:45:00Z",
    details: {
      error: "Plan quota exceeded (READ_ONLY state). Payment required to upload.",
      plan: "FREE",
      file_size_mb: 24.2,
    },
  },
];

export default function GlobalAuditAdminPage() {
  const [logs, setLogs] = useState<AuditLogEntry[]>(MOCK_AUDIT_LOGS);

  const handleExportCSV = () => {
    const headers = ["ID", "Timestamp", "Tenant", "User", "Action", "Resource", "Status", "IP"];
    const rows = logs.map((l) => [
      l.id,
      l.created_at,
      l.tenant_id,
      l.user_email,
      l.action,
      l.resource_type,
      l.status,
      l.ip_address,
    ]);
    const csvContent =
      "data:text/csv;charset=utf-8," +
      [headers.join(","), ...rows.map((e) => e.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `titanrag_audit_log_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-8 p-6 lg:p-10 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2.5">
          <ShieldCheck className="w-7 h-7 text-indigo-400" />
          Global Audit Log Viewer
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Complete compliance trail of all administrative actions, authentication events, and quota modifications.
        </p>
      </div>

      <GlobalAuditTable entries={logs} onExportCSV={handleExportCSV} />
    </div>
  );
}
