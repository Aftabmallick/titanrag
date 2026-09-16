"use client";

import React from "react";
import { Sparkles, ArrowRight } from "lucide-react";

export interface FollowUpSuggestionsProps {
  suggestions: string[];
  onSelectSuggestion: (query: string) => void;
}

export function FollowUpSuggestions({
  suggestions,
  onSelectSuggestion,
}: FollowUpSuggestionsProps) {
  if (!suggestions || suggestions.length === 0) return null;

  return (
    <div className="space-y-2 mt-4 pt-3 border-t border-slate-800/60">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-400">
        <Sparkles className="w-3.5 h-3.5 text-sky-400" />
        <span>Suggested follow-ups</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {suggestions.map((s, idx) => (
          <button
            key={idx}
            onClick={() => onSelectSuggestion(s)}
            className="group flex items-center gap-2 px-3 py-1.5 rounded-xl border border-slate-800 bg-slate-900/60 hover:bg-slate-800 hover:border-slate-700 text-xs text-slate-300 hover:text-white transition-all text-left shadow-sm"
          >
            <span>{s}</span>
            <ArrowRight className="w-3 h-3 text-slate-500 group-hover:text-sky-400 transition-colors" />
          </button>
        ))}
      </div>
    </div>
  );
}
