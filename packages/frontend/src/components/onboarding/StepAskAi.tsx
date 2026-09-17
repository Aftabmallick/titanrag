"use client";

import React from "react";
import { MessageSquare, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/Button";

export interface StepAskAiProps {
  onBack: () => void;
  onFinish: () => void;
}

export function StepAskAi({ onBack, onFinish }: StepAskAiProps) {
  return (
    <div className="space-y-4">
      <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
        <div className="flex items-center gap-2 text-sm font-semibold text-white">
          <MessageSquare className="w-4 h-4 text-sky-400" />
          <span>Ask Grounded Questions</span>
        </div>
        <p className="text-xs text-slate-400 leading-relaxed">
          Every assistant answer is grounded in your verified documents with clickable page citations,
          exact bounding box visual overlays, and NLI verification.
        </p>
      </div>

      <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/80 space-y-2 text-xs text-slate-300">
        <div className="font-semibold text-slate-200">Recommended Next Steps:</div>
        <ul className="space-y-1.5 list-disc list-inside text-slate-400">
          <li>Try asking a domain question in the chat interface.</li>
          <li>Click citation badges [1], [2] to inspect raw document source pages.</li>
          <li>Configure RAG retrieval parameters in Workspace Settings.</li>
        </ul>
      </div>

      <div className="flex justify-between pt-2">
        <Button variant="outline" onClick={onBack}>
          ← Back
        </Button>
        <Button onClick={onFinish} className="gap-2 bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white">
          <Sparkles className="w-4 h-4" />
          <span>Get Started with TitanRAG</span>
        </Button>
      </div>
    </div>
  );
}
