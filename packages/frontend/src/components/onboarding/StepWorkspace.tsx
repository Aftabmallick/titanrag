"use client";

import React from "react";
import { Building } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export interface StepWorkspaceProps {
  workspaceName: string;
  setWorkspaceName: (val: string) => void;
  activeWorkspaceName?: string;
  loading: boolean;
  onNext: () => void;
}

export function StepWorkspace({
  workspaceName,
  setWorkspaceName,
  activeWorkspaceName,
  loading,
  onNext,
}: StepWorkspaceProps) {
  return (
    <div className="space-y-4">
      <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
        <div className="flex items-center gap-2 text-sm font-semibold text-white">
          <Building className="w-4 h-4 text-sky-400" />
          <span>Name Your First Workspace</span>
        </div>
        <p className="text-xs text-slate-400 leading-relaxed">
          Workspaces strictly isolate documents, embeddings, and chat histories across different
          departments or business units.
        </p>
      </div>

      <div className="space-y-1.5">
        <label className="text-xs font-semibold text-slate-300">Workspace Name</label>
        <Input
          placeholder={activeWorkspaceName || "e.g. Legal & Contracts"}
          value={workspaceName}
          onChange={(e) => setWorkspaceName(e.target.value)}
          autoFocus
        />
      </div>

      <div className="flex justify-end pt-2">
        <Button onClick={onNext} disabled={loading} className="gap-2">
          {loading ? "Creating..." : "Continue to Documents →"}
        </Button>
      </div>
    </div>
  );
}
