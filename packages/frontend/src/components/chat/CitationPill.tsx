"use client";

import React, { useState } from "react";
import { FileText, CheckCircle2, AlertCircle } from "lucide-react";
import { CitationPayload } from "@/lib/api";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: any[]) {
  return twMerge(clsx(inputs));
}

export interface CitationPillProps {
  sourceIndex: number;
  citation?: CitationPayload;
  onClick: (citation: CitationPayload) => void;
}

export function CitationPill({ sourceIndex, citation, onClick }: CitationPillProps) {
  const [showTooltip, setShowTooltip] = useState(false);

  if (!citation) {
    return (
      <span className="inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-mono bg-sky-500/10 text-sky-400 border border-sky-500/20 font-bold mx-0.5 align-baseline">
        [{sourceIndex}]
      </span>
    );
  }

  const isVerified = citation.verified;
  const entailment = citation.entailment_score;

  return (
    <span className="relative inline-block align-baseline mx-0.5">
      <button
        type="button"
        onClick={() => onClick(citation)}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        className={cn(
          "inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[11px] font-medium transition-all duration-150 cursor-pointer shadow-sm",
          isVerified
            ? "bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/30"
            : "bg-sky-500/15 hover:bg-sky-500/25 text-sky-300 border border-sky-500/30"
        )}
      >
        <FileText className="w-3 h-3 shrink-0 opacity-75" />
        <span className="font-mono font-bold text-[10px]">[{sourceIndex}]</span>
        {isVerified && (
          <CheckCircle2 className="w-2.5 h-2.5 text-emerald-400 shrink-0" />
        )}
      </button>

      {/* Hover Preview Tooltip */}
      {showTooltip && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2.5 rounded-xl bg-slate-900 border border-slate-700/80 shadow-2xl z-50 text-left pointer-events-none space-y-1.5 backdrop-blur-md">
          <div className="flex items-center justify-between text-[10px] text-slate-400 border-b border-slate-800 pb-1">
            <span className="font-semibold text-slate-200 truncate max-w-[140px]">
              {citation.document_name}
            </span>
            {citation.page_number && (
              <span className="bg-slate-800 px-1.5 py-0.5 rounded text-sky-400 font-mono">
                Page {citation.page_number}
              </span>
            )}
          </div>
          <p className="text-[11px] text-slate-300 line-clamp-3 leading-relaxed">
            &ldquo;{citation.snippet}&rdquo;
          </p>
          <div className="flex items-center justify-between text-[10px] pt-1 text-slate-400">
            <span>Score: {(citation.relevance_score * 100).toFixed(0)}%</span>
            {isVerified && (
              <span className="text-emerald-400 font-semibold flex items-center gap-1">
                <CheckCircle2 className="w-2.5 h-2.5" />
                <span>NLI Verified</span>
              </span>
            )}
          </div>
        </div>
      )}
    </span>
  );
}
