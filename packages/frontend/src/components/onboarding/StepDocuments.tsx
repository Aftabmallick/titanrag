"use client";

import React from "react";
import { UploadCloud, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/Button";

export interface StepDocumentsProps {
  onBack: () => void;
  onNext: () => void;
}

export function StepDocuments({ onBack, onNext }: StepDocumentsProps) {
  return (
    <div className="space-y-4">
      <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
        <div className="flex items-center gap-2 text-sm font-semibold text-white">
          <UploadCloud className="w-4 h-4 text-sky-400" />
          <span>Upload or Ingest Documents</span>
        </div>
        <p className="text-xs text-slate-400 leading-relaxed">
          TitanRAG processes PDFs, Word, Markdown, and Scanned Documents using OCR, contextual
          chunking, and dense+sparse vector indexing.
        </p>
      </div>

      <div className="border-2 border-dashed border-slate-800 rounded-xl p-6 text-center space-y-2">
        <UploadCloud className="w-8 h-8 text-slate-500 mx-auto" />
        <p className="text-xs text-slate-300 font-medium">
          You can upload files anytime via the Documents sidebar or use pre-loaded demo files.
        </p>
        <div className="flex items-center justify-center gap-4 text-[11px] text-slate-400 pt-2">
          <span className="flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Auto OCR
          </span>
          <span className="flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> PII Masking
          </span>
          <span className="flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Near-Dedup
          </span>
        </div>
      </div>

      <div className="flex justify-between pt-2">
        <Button variant="outline" onClick={onBack}>
          ← Back
        </Button>
        <Button onClick={onNext}>Continue to Chat →</Button>
      </div>
    </div>
  );
}
