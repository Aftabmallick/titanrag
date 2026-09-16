"use client";

import React from "react";
import { Zap, Brain, Sparkles, Shield, Sliders } from "lucide-react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: any[]) {
  return twMerge(clsx(inputs));
}

export interface ChatControlsBarProps {
  pipelineMode: "auto" | "fast" | "deep";
  setPipelineMode: (mode: "auto" | "fast" | "deep") => void;
  groundingMode: "strict" | "balanced" | "creative";
  setGroundingMode: (mode: "strict" | "balanced" | "creative") => void;
  onOpenSettingsDrawer?: () => void;
}

export function ChatControlsBar({
  pipelineMode,
  setPipelineMode,
  groundingMode,
  setGroundingMode,
  onOpenSettingsDrawer,
}: ChatControlsBarProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 px-1 py-1.5 text-xs">
      {/* Pipeline Mode Switcher */}
      <div className="flex items-center gap-1 bg-slate-900/80 p-0.5 rounded-xl border border-slate-800">
        <button
          type="button"
          onClick={() => setPipelineMode("auto")}
          className={cn(
            "flex items-center gap-1.5 px-2.5 py-1 rounded-lg font-semibold transition-colors",
            pipelineMode === "auto"
              ? "bg-slate-800 text-sky-400 shadow-sm"
              : "text-slate-400 hover:text-slate-200"
          )}
        >
          <Sparkles className="w-3 h-3 text-sky-400" />
          <span>Auto</span>
        </button>

        <button
          type="button"
          onClick={() => setPipelineMode("fast")}
          className={cn(
            "flex items-center gap-1.5 px-2.5 py-1 rounded-lg font-semibold transition-colors",
            pipelineMode === "fast"
              ? "bg-slate-800 text-amber-400 shadow-sm"
              : "text-slate-400 hover:text-slate-200"
          )}
        >
          <Zap className="w-3 h-3 text-amber-400" />
          <span>Fast (&lt;1.8s)</span>
        </button>

        <button
          type="button"
          onClick={() => setPipelineMode("deep")}
          className={cn(
            "flex items-center gap-1.5 px-2.5 py-1 rounded-lg font-semibold transition-colors",
            pipelineMode === "deep"
              ? "bg-slate-800 text-indigo-400 shadow-sm"
              : "text-slate-400 hover:text-slate-200"
          )}
        >
          <Brain className="w-3 h-3 text-indigo-400" />
          <span>Deep Reasoning</span>
        </button>
      </div>

      {/* Grounding Mode & Settings trigger */}
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1.5 bg-slate-900/80 px-2.5 py-1 rounded-xl border border-slate-800 text-slate-400">
          <Shield className="w-3 h-3 text-emerald-400" />
          <span className="text-[11px]">Grounding:</span>
          <select
            value={groundingMode}
            onChange={(e) => setGroundingMode(e.target.value as any)}
            className="bg-transparent text-[11px] font-semibold text-slate-200 focus:outline-none cursor-pointer"
          >
            <option value="strict" className="bg-slate-900 text-slate-200">
              Strict
            </option>
            <option value="balanced" className="bg-slate-900 text-slate-200">
              Balanced
            </option>
            <option value="creative" className="bg-slate-900 text-slate-200">
              Creative
            </option>
          </select>
        </div>

        {onOpenSettingsDrawer && (
          <button
            type="button"
            onClick={onOpenSettingsDrawer}
            className="p-1.5 rounded-xl border border-slate-800 bg-slate-900/80 hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
            title="Configure RAG Parameters"
          >
            <Sliders className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}
