"use client";

import React from "react";
import { Award, CheckCircle, AlertTriangle, Shield, Cpu, HelpCircle } from "lucide-react";

export interface DeepEvalScores {
  faithfulness_deepeval: number;
  contextual_relevancy_deepeval: number;
  coherence_deepeval: number;
  hallucination_deepeval: number;
  is_degraded?: boolean;
}

interface DeepEvalMetricsCardProps {
  scores: DeepEvalScores;
  ragasFaithfulness?: number;
  ragasRelevancy?: number;
}

export function DeepEvalMetricsCard({
  scores,
  ragasFaithfulness = 0.94,
  ragasRelevancy = 0.88,
}: DeepEvalMetricsCardProps) {
  const formatPercent = (val: number) => `${Math.round(val * 100)}%`;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-6 shadow-xl space-y-6">
      <div className="flex items-center justify-between pb-4 border-b border-slate-800/80">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-slate-100">
              DeepEval & G-Eval Assessment
            </h3>
            <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-purple-950/60 text-purple-300 border border-purple-800/50">
              Multi-Framework V2
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            G-Eval coherence, hallucination rates, and contextual alignment evaluated via LLM judge.
          </p>
        </div>

        {scores.is_degraded ? (
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs bg-amber-950/60 text-amber-300 border border-amber-800/50">
            <AlertTriangle className="w-3.5 h-3.5" />
            Heuristic Mode
          </span>
        ) : (
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs bg-emerald-950/60 text-emerald-300 border border-emerald-800/50">
            <CheckCircle className="w-3.5 h-3.5" />
            Evaluated with GPT-4o-mini
          </span>
        )}
      </div>

      {/* Grid of Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-1">
          <div className="text-xs text-slate-400">Faithfulness</div>
          <div className="text-2xl font-bold text-emerald-400">
            {formatPercent(scores.faithfulness_deepeval)}
          </div>
          <div className="text-[11px] text-slate-500">
            RAGAS: {formatPercent(ragasFaithfulness)}
          </div>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-1">
          <div className="text-xs text-slate-400">Contextual Relevancy</div>
          <div className="text-2xl font-bold text-indigo-400">
            {formatPercent(scores.contextual_relevancy_deepeval)}
          </div>
          <div className="text-[11px] text-slate-500">
            RAGAS: {formatPercent(ragasRelevancy)}
          </div>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-1">
          <div className="text-xs text-slate-400">G-Eval Coherence</div>
          <div className="text-2xl font-bold text-purple-400">
            {formatPercent(scores.coherence_deepeval)}
          </div>
          <div className="text-[11px] text-slate-500">Semantic Flow</div>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-1">
          <div className="text-xs text-slate-400">Hallucination Risk</div>
          <div className="text-2xl font-bold text-slate-200">
            {formatPercent(scores.hallucination_deepeval)}
          </div>
          <div className="text-[11px] text-emerald-400">Lower is better</div>
        </div>
      </div>
    </div>
  );
}
