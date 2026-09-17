"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft, MessageSquareQuote } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { FeedbackTriageTable } from "@/components/analytics/FeedbackTriageTable";

export default function FeedbackAnalyticsPage() {
  const { activeWorkspace } = useAuth();

  return (
    <div className="flex-1 overflow-y-auto p-6 md:p-8 space-y-6 bg-slate-950">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/analytics"
            className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-white transition"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              <MessageSquareQuote className="w-5 h-5 text-sky-400" />
              <span>Feedback & Quality Studio</span>
            </h1>
            <p className="text-xs text-slate-400">
              Inspect user satisfaction ratings, reported citation errors, and promote fixes directly into evaluation suites.
            </p>
          </div>
        </div>
      </div>

      <FeedbackTriageTable workspaceId={activeWorkspace?.id} />
    </div>
  );
}
