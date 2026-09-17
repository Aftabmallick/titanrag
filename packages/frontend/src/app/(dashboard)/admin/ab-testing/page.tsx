"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft, Split } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { VariantComparisonCard } from "@/components/ab_testing/VariantComparisonCard";

export default function ABTestingAdminPage() {
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
            <Split className="w-5 h-5 text-sky-400" />
            <span>RAG A/B Testing & Statistical Experimentation</span>
          </h1>
          <p className="text-xs text-slate-400">
            Deploy deterministic traffic splits with MurmurHash3 and evaluate statistical significance ($p &lt; 0.05$) across retrieval parameters.
          </p>
        </div>
      </div>

      <VariantComparisonCard workspaceId={activeWorkspace?.id} />
    </div>
  );
}
