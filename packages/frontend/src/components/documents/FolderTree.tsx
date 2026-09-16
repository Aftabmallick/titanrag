"use client";

import React, { useState } from "react";
import { Folder, FolderPlus, FolderOpen, ChevronRight, ChevronDown, Check, Plus } from "lucide-react";
import { DocumentRecord } from "@/lib/api";

export interface FolderTreeProps {
  documents: DocumentRecord[];
  activeFolder: string;
  onSelectFolder: (folder: string) => void;
  onCreateFolder?: (folderName: string) => void;
}

export function FolderTree({
  documents,
  activeFolder,
  onSelectFolder,
  onCreateFolder,
}: FolderTreeProps) {
  const [newFolderOpen, setNewFolderOpen] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");

  // Aggregate document counts per folder
  const folderCounts: Record<string, number> = {};
  documents.forEach((d) => {
    const f = d.folder || "Uncategorized";
    folderCounts[f] = (folderCounts[f] || 0) + 1;
  });

  const folderNames = Object.keys(folderCounts).sort();

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFolderName.trim()) return;
    onCreateFolder?.(newFolderName.trim());
    onSelectFolder(newFolderName.trim());
    setNewFolderName("");
    setNewFolderOpen(false);
  };

  return (
    <div className="w-60 bg-slate-950/60 border border-slate-800/80 rounded-2xl p-3 space-y-3 shrink-0">
      <div className="flex items-center justify-between px-2 pb-1 border-b border-slate-800/60">
        <div className="flex items-center gap-2 text-xs font-bold text-slate-300">
          <Folder className="w-3.5 h-3.5 text-sky-400" />
          <span>Folders</span>
        </div>
        <button
          onClick={() => setNewFolderOpen((prev) => !prev)}
          className="p-1 rounded-lg text-slate-400 hover:text-sky-400 hover:bg-slate-800 transition-colors"
          title="New Folder"
        >
          <FolderPlus className="w-3.5 h-3.5" />
        </button>
      </div>

      {newFolderOpen && (
        <form onSubmit={handleCreate} className="flex items-center gap-1">
          <input
            type="text"
            value={newFolderName}
            onChange={(e) => setNewFolderName(e.target.value)}
            placeholder="Folder name..."
            autoFocus
            className="flex-1 px-2 py-1 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white focus:outline-none focus:border-sky-500"
          />
          <button
            type="submit"
            className="p-1 rounded-lg bg-sky-500 hover:bg-sky-400 text-white"
          >
            <Check className="w-3.5 h-3.5" />
          </button>
        </form>
      )}

      <div className="space-y-0.5">
        {/* All Documents */}
        <button
          onClick={() => onSelectFolder("ALL")}
          className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-xl text-xs font-medium transition-colors ${
            activeFolder === "ALL"
              ? "bg-sky-500/10 text-sky-400 border border-sky-500/20 font-semibold"
              : "text-slate-300 hover:bg-slate-900 hover:text-white"
          }`}
        >
          <div className="flex items-center gap-2">
            <FolderOpen className="w-3.5 h-3.5 text-sky-400" />
            <span>All Documents</span>
          </div>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
            {documents.length}
          </span>
        </button>

        {/* Individual Folders */}
        {folderNames.map((f) => (
          <button
            key={f}
            onClick={() => onSelectFolder(f)}
            className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-xl text-xs font-medium transition-colors ${
              activeFolder === f
                ? "bg-sky-500/10 text-sky-400 border border-sky-500/20 font-semibold"
                : "text-slate-300 hover:bg-slate-900 hover:text-white"
            }`}
          >
            <div className="flex items-center gap-2 truncate">
              <Folder className="w-3.5 h-3.5 text-slate-400" />
              <span className="truncate">{f}</span>
            </div>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
              {folderCounts[f]}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
