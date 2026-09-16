"use client";

import React, { useState, useRef, useEffect } from "react";
import { RotateCcw, Sparkles, RefreshCw, ChevronDown } from "lucide-react";

export interface RegenerateDropdownProps {
  onRegenerateSameSources: () => void;
  onRetryFreshRetrieval: () => void;
}

export function RegenerateDropdown({
  onRegenerateSameSources,
  onRetryFreshRetrieval,
}: RegenerateDropdownProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="relative inline-block" ref={ref}>
      <button
        onClick={() => setOpen((prev) => !prev)}
        className="flex items-center gap-1 p-1.5 rounded-lg text-slate-500 hover:text-sky-400 hover:bg-slate-800 transition-colors"
        title="Regenerate Response"
        aria-label="Regenerate Response Options"
      >
        <RotateCcw className="w-3.5 h-3.5" />
        <ChevronDown className="w-2.5 h-2.5 opacity-60" />
      </button>

      {open && (
        <div className="absolute right-0 bottom-full mb-1.5 w-60 rounded-xl border border-slate-800 bg-slate-900 shadow-2xl p-1.5 z-50 animate-in fade-in zoom-in-95 duration-100 text-left">
          <div className="px-2 py-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
            Regeneration Modes
          </div>

          <button
            onClick={() => {
              setOpen(false);
              onRegenerateSameSources();
            }}
            className="w-full flex items-start gap-2.5 p-2 rounded-lg hover:bg-slate-800 text-left transition-colors group"
          >
            <Sparkles className="w-3.5 h-3.5 text-sky-400 mt-0.5 shrink-0" />
            <div>
              <div className="text-xs font-semibold text-slate-200 group-hover:text-white">
                Regenerate with Same Sources
              </div>
              <div className="text-[10px] text-slate-400">
                Re-synthesize answer preserving locked chunk context
              </div>
            </div>
          </button>

          <button
            onClick={() => {
              setOpen(false);
              onRetryFreshRetrieval();
            }}
            className="w-full flex items-start gap-2.5 p-2 rounded-lg hover:bg-slate-800 text-left transition-colors group"
          >
            <RefreshCw className="w-3.5 h-3.5 text-indigo-400 mt-0.5 shrink-0" />
            <div>
              <div className="text-xs font-semibold text-slate-200 group-hover:text-white">
                Retry with Fresh Retrieval
              </div>
              <div className="text-[10px] text-slate-400">
                Execute fresh hybrid search & reranking pipeline
              </div>
            </div>
          </button>
        </div>
      )}
    </div>
  );
}
