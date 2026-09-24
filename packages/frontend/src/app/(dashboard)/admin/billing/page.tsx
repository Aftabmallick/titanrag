"use client";

import React, { useState } from "react";
import { PlanUsageCard } from "@/components/billing/PlanUsageCard";
import { InvoiceTable } from "@/components/billing/InvoiceTable";
import { PlanUpgradeModal } from "@/components/billing/PlanUpgradeModal";
import { CreditCard, FileText, BarChart3, Settings } from "lucide-react";

export default function BillingPage() {
  const [upgradeModalOpen, setUpgradeModalOpen] = useState(false);
  const [currentPlan, setCurrentPlan] = useState("FREE");

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-8">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 flex items-center justify-center">
              <CreditCard className="w-5 h-5 text-white" />
            </div>
            Billing & Usage
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Manage your subscription, monitor Compute Unit usage, and download invoices.
          </p>
        </div>
        <button
          id="billing-manage-btn"
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium text-slate-300 border border-slate-700/60 hover:bg-slate-800/60 transition-all duration-200"
          onClick={async () => {
            const res = await fetch(
              `/api/v1/billing/portal?return_url=${encodeURIComponent(window.location.href)}`,
              {
                method: "POST",
                headers: { Authorization: `Bearer ${localStorage.getItem("titan_token")}` },
              }
            );
            if (res.ok) {
              const { portal_url } = await res.json();
              window.location.href = portal_url;
            }
          }}
        >
          <Settings className="w-4 h-4" />
          Manage Payment Method
        </button>
      </div>

      {/* 2-column grid: plan card + usage breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <PlanUsageCard />
          <button
            id="billing-upgrade-plan-btn"
            onClick={() => setUpgradeModalOpen(true)}
            className="w-full py-3 rounded-xl text-sm font-semibold bg-gradient-to-r from-indigo-600 to-violet-600 text-white hover:from-indigo-500 hover:to-violet-500 transition-all duration-200 shadow-lg shadow-indigo-500/20 hover:shadow-indigo-500/30"
          >
            View All Plans & Upgrade
          </button>
        </div>

        {/* Usage breakdown card */}
        <UsageBreakdownCard />
      </div>

      {/* Invoice history */}
      <div className="glass-card rounded-2xl border border-slate-700/50 p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-8 h-8 rounded-lg bg-slate-700/60 flex items-center justify-center">
            <FileText className="w-4 h-4 text-slate-400" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-100">Invoice History</h2>
            <p className="text-xs text-slate-500">Download PDFs or view invoices on Stripe</p>
          </div>
        </div>
        <InvoiceTable />
      </div>

      {/* Upgrade modal */}
      <PlanUpgradeModal
        currentPlan={currentPlan}
        isOpen={upgradeModalOpen}
        onClose={() => setUpgradeModalOpen(false)}
      />
    </div>
  );
}

function UsageBreakdownCard() {
  const [usage, setUsage] = React.useState<Record<string, number> | null>(null);
  const [total, setTotal] = React.useState(0);

  React.useEffect(() => {
    fetch("/api/v1/billing/usage", {
      headers: { Authorization: `Bearer ${localStorage.getItem("titan_token")}` },
    })
      .then((r) => r.json())
      .then((data) => {
        setUsage(data.breakdown || {});
        setTotal(data.total_cu || 0);
      })
      .catch(() => {});
  }, []);

  const categories = [
    { key: "generation", label: "LLM Generation", color: "bg-indigo-500" },
    { key: "retrieval", label: "Retrieval", color: "bg-violet-500" },
    { key: "ingestion_ocr", label: "OCR Ingestion", color: "bg-emerald-500" },
    { key: "contextual_prefix", label: "Contextual Prefixes", color: "bg-amber-500" },
    { key: "colpali_visual", label: "ColPali Visual", color: "bg-pink-500" },
    { key: "reranking", label: "Reranking", color: "bg-sky-500" },
  ];

  return (
    <div className="glass-card rounded-2xl border border-slate-700/50 p-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-8 rounded-lg bg-slate-700/60 flex items-center justify-center">
          <BarChart3 className="w-4 h-4 text-slate-400" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-slate-100">Usage Breakdown</h2>
          <p className="text-xs text-slate-500">This billing period · {total.toLocaleString()} CU total</p>
        </div>
      </div>

      {!usage ? (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-8 bg-slate-700/40 rounded animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {categories.map(({ key, label, color }) => {
            const val = usage[key] || 0;
            const pct = total > 0 ? (val / total) * 100 : 0;
            return (
              <div key={key}>
                <div className="flex justify-between mb-1">
                  <span className="text-xs text-slate-400">{label}</span>
                  <span className="text-xs font-medium text-slate-300">
                    {val.toFixed(1)} CU ({pct.toFixed(1)}%)
                  </span>
                </div>
                <div className="h-1.5 bg-slate-700/60 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${color} rounded-full transition-all duration-700`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
