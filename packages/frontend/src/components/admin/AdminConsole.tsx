"use client";

import React, { useState } from "react";
import { Tabs } from "@/components/ui/Tabs";
import { HealthView } from "@/components/HealthView";
import { DlqView } from "@/components/DlqView";
import { ApiKeysView } from "@/components/ApiKeysView";
import { Button } from "@/components/ui/Button";
import { TenantQuotaModal } from "./TenantQuotaModal";
import { ShieldAlert, Activity, AlertOctagon, Key, ShieldCheck, Sliders } from "lucide-react";

export function AdminConsole() {
  const [activeTab, setActiveTab] = useState<"health" | "dlq" | "apikeys">("health");
  const [quotaModalOpen, setQuotaModalOpen] = useState(false);

  const tabs = [
    { id: "health" as const, label: "Core Health & Dependencies", icon: <Activity className="w-3.5 h-3.5" /> },
    { id: "dlq" as const, label: "Dead-Letter Queue (DLQ)", icon: <AlertOctagon className="w-3.5 h-3.5" /> },
    { id: "apikeys" as const, label: "API Keys & Service Accounts", icon: <Key className="w-3.5 h-3.5" /> },
  ];

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-sky-400" />
            <span>Platform Administration & Observability</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Manage infrastructure dependencies, Celery dead-letter tasks, and scoped API credentials.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={() => setQuotaModalOpen(true)}
          icon={<Sliders className="w-3.5 h-3.5 text-sky-400" />}
        >
          Tenant Quotas & SCIM
        </Button>
      </div>

      {/* Tabs */}
      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

      {/* Tab Panels */}
      <div>
        {activeTab === "health" && <HealthView />}
        {activeTab === "dlq" && <DlqView />}
        {activeTab === "apikeys" && <ApiKeysView />}
      </div>

      {/* Tenant Quota & SCIM Modal */}
      <TenantQuotaModal
        isOpen={quotaModalOpen}
        onClose={() => setQuotaModalOpen(false)}
      />
    </div>
  );
}
