"use client";

import React, { useState } from "react";
import { RefreshCw, Trash2, FolderInput, X, Check } from "lucide-react";
import { Button } from "@/components/ui/Button";

export interface BulkActionToolbarProps {
  selectedCount: number;
  onClearSelection: () => void;
  onBulkReindex: () => Promise<void>;
  onBulkDelete: () => Promise<void>;
  onBulkMoveFolder: (folderName: string) => Promise<void>;
  availableFolders: string[];
}

export function BulkActionToolbar({
  selectedCount,
  onClearSelection,
  onBulkReindex,
  onBulkDelete,
  onBulkMoveFolder,
  availableFolders,
}: BulkActionToolbarProps) {
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [moveFolderOpen, setMoveFolderOpen] = useState(false);
  const [targetFolder, setTargetFolder] = useState(availableFolders[0] || "General");

  if (selectedCount === 0) return null;

  const handleReindex = async () => {
    setLoadingAction("reindex");
    try {
      await onBulkReindex();
    } finally {
      setLoadingAction(null);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Are you sure you want to delete ${selectedCount} selected document(s)? This action removes vector projections.`)) {
      return;
    }
    setLoadingAction("delete");
    try {
      await onBulkDelete();
    } finally {
      setLoadingAction(null);
    }
  };

  const handleMove = async () => {
    setLoadingAction("move");
    try {
      await onBulkMoveFolder(targetFolder);
      setMoveFolderOpen(false);
    } finally {
      setLoadingAction(null);
    }
  };

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 flex items-center gap-3 px-5 py-3 rounded-2xl bg-slate-900/95 border border-slate-700 shadow-2xl backdrop-blur-2xl text-xs animate-in fade-in slide-in-from-bottom-3 duration-200">
      <div className="flex items-center gap-2 pr-3 border-r border-slate-800">
        <span className="w-2 h-2 rounded-full bg-sky-400 animate-pulse" />
        <span className="font-bold text-white">
          {selectedCount} document{selectedCount > 1 ? "s" : ""} selected
        </span>
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          loading={loadingAction === "reindex"}
          onClick={handleReindex}
          icon={<RefreshCw className="w-3.5 h-3.5 text-sky-400" />}
        >
          Bulk Re-index
        </Button>

        {moveFolderOpen ? (
          <div className="flex items-center gap-1">
            <select
              value={targetFolder}
              onChange={(e) => setTargetFolder(e.target.value)}
              className="bg-slate-800 text-slate-200 border border-slate-700 rounded-lg px-2 py-1 text-xs focus:outline-none"
            >
              {availableFolders.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
              <option value="General">General</option>
            </select>
            <button
              onClick={handleMove}
              className="p-1.5 rounded-lg bg-sky-500 hover:bg-sky-400 text-white"
            >
              <Check className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setMoveFolderOpen(false)}
              className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setMoveFolderOpen(true)}
            icon={<FolderInput className="w-3.5 h-3.5 text-indigo-400" />}
          >
            Move to Folder
          </Button>
        )}

        <Button
          variant="danger"
          size="sm"
          loading={loadingAction === "delete"}
          onClick={handleDelete}
          icon={<Trash2 className="w-3.5 h-3.5" />}
        >
          Bulk Delete
        </Button>

        <button
          onClick={onClearSelection}
          className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors ml-1"
          title="Deselect all"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
