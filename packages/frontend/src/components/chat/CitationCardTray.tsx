"use client";

import React, { useState } from "react";
import { CitationPayload } from "@/lib/api";
import { ChevronDown, ChevronUp, FileText, CheckCircle2, ExternalLink } from "lucide-react";

export interface CitationCardTrayProps {
  citations: CitationPayload[];
  onCitationClick: (citation: CitationPayload) => void;
}

export function CitationCardTray({ citations, onCitationClick }: CitationCardTrayProps) {
  const [expanded, setExpanded] = useState(false);

  if (!citations || citations.length === 0) return null;

  return (
    <div className="mt-3 border-t border-slate-800/80 pt-2.5">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-slate-200 transition-colors"
      >
        <span className="flex items-center gap-1.5">
          <FileText className="w-3.5 h-3.5 text-sky-400" />
          <span>Cited Sources ({citations.length})</span>
        </span>
        {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
      </button>

      {expanded && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 mt-2.5">
          {citations.map((c, i) => (
            <div
              key={`${c.document_id}-${c.source_index}-${i}`}
              onClick={() => onCitationClick(c)}
              className="p-3 rounded-xl border border-slate-800 bg-slate-900/60 hover:bg-slate-850/80 hover:border-slate-700 transition-all cursor-pointer space-y-1.5 group"
            >
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-slate-200 flex items-center gap-1.5 truncate max-w-[180px]">
                  <span className="font-mono text-sky-400 text-[11px]">[{c.source_index}]</span>
                  <span className="truncate">{c.document_name}</span>
                </span>
                {c.page_number && (
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                    p. {c.page_number}
                  </span>
                )}
              </div>

              <p className="text-[11px] text-slate-400 line-clamp-2 leading-relaxed">
                &ldquo;{c.snippet}&rdquo;
              </p>

              <div className="flex items-center justify-between text-[10px] text-slate-500 pt-0.5">
                <span>Score: {(c.relevance_score * 100).toFixed(0)}%</span>
                <div className="flex items-center gap-2">
                  {c.verified && (
                    <span className="text-emerald-400 flex items-center gap-1 font-semibold">
                      <CheckCircle2 className="w-3 h-3" />
                      <span>Verified</span>
                    </span>
                  )}
                  <ExternalLink className="w-3 h-3 text-slate-500 group-hover:text-sky-400 transition-colors" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
