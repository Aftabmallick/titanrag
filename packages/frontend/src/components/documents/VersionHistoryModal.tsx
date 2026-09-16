"use client";

import React from "react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { History, GitCommit, CheckCircle2, Clock, RotateCcw, FileText } from "lucide-react";
import { DocumentRecord } from "@/lib/api";

export interface VersionHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  document: DocumentRecord | null;
}

export function VersionHistoryModal({
  isOpen,
  onClose,
  document,
}: VersionHistoryModalProps) {
  if (!document) return null;

  // Versions history simulation matching backend document_versions schema
  const versions = [
    {
      version: 2,
      isCurrent: true,
      timestamp: document.updated_at,
      chunksCount: 24,
      changesSummary: "Updated Section 12 indemnification clause & delta re-embedded via MinHash LSH",
    },
    {
      version: 1,
      isCurrent: false,
      timestamp: document.created_at,
      chunksCount: 22,
      changesSummary: "Initial ingestion and structural Docling parsing",
    },
  ];

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex items-center gap-2">
          <History className="w-5 h-5 text-sky-400" />
          <span>Version History: {document.title}</span>
        </div>
      }
      description="Track delta updates, MinHash re-embedding events, and rollback previous document versions."
      maxWidth="lg"
    >
      <div className="space-y-4 py-2">
        <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 text-xs text-slate-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-sky-400" />
            <span className="font-semibold">{document.title}</span>
          </div>
          <span className="text-[10px] font-mono text-slate-500">ID: {document.id}</span>
        </div>

        <div className="divide-y divide-slate-800 border-t border-b border-slate-800">
          {versions.map((v) => (
            <div key={v.version} className="py-3.5 space-y-1.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-sky-500/10 text-sky-400 border border-sky-500/20">
                    Version v{v.version}
                  </span>
                  {v.isCurrent && (
                    <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-400">
                      <CheckCircle2 className="w-3 h-3" />
                      <span>Active in Vector Store</span>
                    </span>
                  )}
                </div>
                <span className="text-[11px] font-mono text-slate-500">
                  {new Date(v.timestamp).toLocaleString()}
                </span>
              </div>

              <p className="text-xs text-slate-300">{v.changesSummary}</p>
              <div className="flex items-center justify-between text-[11px] text-slate-500">
                <span>{v.chunksCount} Qdrant projection chunks</span>
                {!v.isCurrent && (
                  <button
                    type="button"
                    onClick={() => alert(`Rolled back to v${v.version}. Re-activating archived chunks in Qdrant.`)}
                    className="inline-flex items-center gap-1 text-sky-400 hover:text-sky-300 font-semibold"
                  >
                    <RotateCcw className="w-3 h-3" />
                    <span>Rollback to this version</span>
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="flex justify-end pt-2">
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </Modal>
  );
}
