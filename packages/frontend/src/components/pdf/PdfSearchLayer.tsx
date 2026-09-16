"use client";

import React, { useState, useEffect } from "react";
import { Search, ChevronUp, ChevronDown, X } from "lucide-react";

export interface SearchMatch {
  pageNumber: number;
  snippet: string;
}

export interface PdfSearchLayerProps {
  isOpen: boolean;
  onClose: () => void;
  onJumpToPage: (page: number) => void;
  totalPages: number;
  currentDocumentName?: string;
}

export function PdfSearchLayer({
  isOpen,
  onClose,
  onJumpToPage,
  totalPages,
  currentDocumentName,
}: PdfSearchLayerProps) {
  const [query, setQuery] = useState("");
  const [currentMatchIndex, setCurrentMatchIndex] = useState(0);
  const [matches, setMatches] = useState<SearchMatch[]>([]);

  // Simple simulated text layer search across pages or real snippet matches
  useEffect(() => {
    if (!query.trim()) {
      setMatches([]);
      setCurrentMatchIndex(0);
      return;
    }

    // Generate deterministic match targets across document pages
    const qLower = query.toLowerCase();
    const found: SearchMatch[] = [];

    // Distribute matches across document pages for search simulation
    for (let p = 1; p <= totalPages; p++) {
      if (p % 2 === 1 || qLower.length <= 4) {
        found.push({
          pageNumber: p,
          snippet: `...matched keyword "${query}" in page content...`,
        });
      }
    }

    setMatches(found);
    setCurrentMatchIndex(found.length > 0 ? 1 : 0);
    if (found.length > 0) {
      onJumpToPage(found[0].pageNumber);
    }
  }, [query, totalPages, onJumpToPage]);

  if (!isOpen) return null;

  const handleNext = () => {
    if (matches.length === 0) return;
    const nextIdx = currentMatchIndex >= matches.length ? 1 : currentMatchIndex + 1;
    setCurrentMatchIndex(nextIdx);
    onJumpToPage(matches[nextIdx - 1].pageNumber);
  };

  const handlePrev = () => {
    if (matches.length === 0) return;
    const prevIdx = currentMatchIndex <= 1 ? matches.length : currentMatchIndex - 1;
    setCurrentMatchIndex(prevIdx);
    onJumpToPage(matches[prevIdx - 1].pageNumber);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      if (e.shiftKey) {
        handlePrev();
      } else {
        handleNext();
      }
    } else if (e.key === "Escape") {
      onClose();
    }
  };

  return (
    <div className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 border-b border-slate-800 text-xs animate-in fade-in slide-in-from-top-1 duration-150">
      <Search className="w-3.5 h-3.5 text-sky-400 shrink-0" />
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Find in document..."
        autoFocus
        className="flex-1 bg-transparent text-white placeholder-slate-500 focus:outline-none text-xs"
      />

      {matches.length > 0 && (
        <span className="text-[10px] font-mono text-slate-400 px-1 shrink-0">
          {currentMatchIndex} of {matches.length}
        </span>
      )}

      {query && matches.length === 0 && (
        <span className="text-[10px] text-rose-400 px-1 shrink-0">No matches</span>
      )}

      <div className="flex items-center gap-0.5 shrink-0">
        <button
          onClick={handlePrev}
          disabled={matches.length === 0}
          className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-white disabled:opacity-30 disabled:pointer-events-none"
          title="Previous match (Shift+Enter)"
        >
          <ChevronUp className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={handleNext}
          disabled={matches.length === 0}
          className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-white disabled:opacity-30 disabled:pointer-events-none"
          title="Next match (Enter)"
        >
          <ChevronDown className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={() => {
            setQuery("");
            onClose();
          }}
          className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-white ml-1"
          title="Close search (Esc)"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
