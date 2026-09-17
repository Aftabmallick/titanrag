"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ArrowLeft, Target } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { RagasRadarChart } from "@/components/evaluation/RagasRadarChart";
import { GoldenDatasetManager } from "@/components/evaluation/GoldenDatasetManager";

export default function EvaluationAnalyticsPage() {
  const { activeWorkspace } = useAuth();
  const [currentScores, setCurrentScores] = useState<any>(null);

  return (
    <div className="flex-1 overflow-y-auto p-6 md:p-8 space-y-8 bg-slate-950">
      <div className="flex items-center gap-3">
        <Link
          href="/analytics"
          className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-white transition"
        >
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Target className="w-5 h-5 text-sky-400" />
            <span>Automated RAGAS & IR Evaluation Benchmarks</span>
          </h1>
          <p className="text-xs text-slate-400">
            Measure Faithfulness, Answer Relevancy, Context Precision, and NDCG@5 against curated golden datasets.
          </p>
        </div>
      </div>

      {/* Radar Chart */}
      <RagasRadarChart scores={currentScores} />

      {/* Golden Dataset Management & Benchmark Triggers */}
      <GoldenDatasetManager
        workspaceId={activeWorkspace?.id}
        onSelectRun={(scores) => setCurrentScores(scores)}
      />
    </div>
  );
}
