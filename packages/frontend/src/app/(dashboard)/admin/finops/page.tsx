"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft, DollarSign } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { ComputeUnitGauge } from "@/components/finops/ComputeUnitGauge";
import { CostAttributionChart } from "@/components/finops/CostAttributionChart";

export default function FinOpsAdminPage() {
  const { activeWorkspace } = useAuth();

  return (
    <div className="flex-1 overflow-y-auto p-6 md:p-8 space-y-8 bg-slate-950">
      <div className="flex items-center gap-3">
        <Link
          href="/admin"
          className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-white transition"
        >
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <DollarSign className="w-5 h-5 text-sky-400" />
            <span>FinOps & Compute Unit (CU) Accounting</span>
          </h1>
          <p className="text-xs text-slate-400">
            Monitor real-time token spend, GPU inference seconds, monthly budget caps, and atomic Redis quota guards.
          </p>
        </div>
      </div>

      <ComputeUnitGauge workspaceId={activeWorkspace?.id} />
      <CostAttributionChart workspaceId={activeWorkspace?.id} />
    </div>
  );
}
