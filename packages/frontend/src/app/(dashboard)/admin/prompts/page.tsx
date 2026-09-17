"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft, Terminal } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { PromptEditorMonaco } from "@/components/prompts/PromptEditorMonaco";
import { PromptDiffViewer } from "@/components/prompts/PromptDiffViewer";

export default function PromptsAdminPage() {
  const { activeWorkspace } = useAuth();

  return (
    <div className="flex-1 overflow-y-auto p-6 md:p-8 space-y-8 bg-slate-950">
      <div className="flex items-center gap-3">
        <Link
          href="/admin"
          className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-white transition"
        >
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Terminal className="w-5 h-5 text-sky-400" />
            <span>PromptOps Registry & Versioning</span>
          </h1>
          <p className="text-xs text-slate-400">
            Edit, test, and hot-reload sandboxed Jinja2 system prompts with zero-downtime promotion across DEV, STAGING, and PROD.
          </p>
        </div>
      </div>

      <PromptEditorMonaco workspaceId={activeWorkspace?.id} />

      <PromptDiffViewer workspaceId={activeWorkspace?.id} />
    </div>
  );
}
