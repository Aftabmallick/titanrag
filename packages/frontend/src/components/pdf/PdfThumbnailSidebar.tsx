"use client";

import React from "react";
import { FileText } from "lucide-react";

export interface PdfThumbnailSidebarProps {
  isOpen: boolean;
  totalPages: number;
  currentPage: number;
  onSelectPage: (page: number) => void;
  documentTitle?: string;
}

export function PdfThumbnailSidebar({
  isOpen,
  totalPages,
  currentPage,
  onSelectPage,
  documentTitle,
}: PdfThumbnailSidebarProps) {
  if (!isOpen) return null;

  const pages = Array.from({ length: totalPages }, (_, i) => i + 1);

  return (
    <aside
      aria-label="PDF Page Thumbnails"
      className="w-40 sm:w-44 border-r border-slate-800 bg-slate-950/90 flex flex-col h-full shrink-0 z-10 animate-in slide-in-from-left duration-200"
    >
      <div className="p-3 border-b border-slate-800 text-[11px] font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
        <span>Thumbnails</span>
        <span className="font-mono text-[10px] text-sky-400">{totalPages} pages</span>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {pages.map((p) => {
          const isActive = p === currentPage;
          return (
            <button
              key={p}
              type="button"
              onClick={() => onSelectPage(p)}
              className={`w-full flex flex-col items-center gap-1.5 p-2 rounded-xl border transition-all text-center group cursor-pointer ${
                isActive
                  ? "bg-sky-500/15 border-sky-500 shadow-md shadow-sky-500/10 ring-1 ring-sky-500/40"
                  : "bg-slate-900/60 border-slate-800 hover:border-slate-700 hover:bg-slate-850"
              }`}
            >
              <div
                className={`w-24 h-32 rounded-lg border flex flex-col items-center justify-center p-2 transition-colors ${
                  isActive
                    ? "bg-slate-900 border-sky-500/50 text-sky-400"
                    : "bg-slate-950 border-slate-800 text-slate-600 group-hover:text-slate-400"
                }`}
              >
                <FileText className="w-6 h-6 mb-1 opacity-75" />
                <span className="text-[9px] font-mono text-slate-500 line-clamp-2 px-1">
                  {documentTitle ? documentTitle.slice(0, 14) : `Page ${p}`}
                </span>
              </div>
              <span
                className={`text-[10px] font-mono font-bold ${
                  isActive ? "text-sky-400" : "text-slate-400 group-hover:text-slate-200"
                }`}
              >
                Page {p}
              </span>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
