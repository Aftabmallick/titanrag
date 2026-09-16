"use client";

import React, { useState } from "react";
import { ChatMessage } from "@/hooks/useChatStream";
import { CitationPayload, api } from "@/lib/api";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { CitationCardTray } from "./CitationCardTray";
import { RegenerateDropdown } from "./RegenerateDropdown";
import { FeedbackModal } from "./FeedbackModal";
import {
  Sparkles,
  User,
  ThumbsUp,
  ThumbsDown,
  Copy,
  Check,
  RotateCcw,
  CheckCircle2,
  Clock,
  Zap,
} from "lucide-react";
import { useToast } from "@/components/ui/Toast";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: any[]) {
  return twMerge(clsx(inputs));
}

export interface MessageItemProps {
  message: ChatMessage;
  workspaceId?: string;
  onCitationClick: (citation: CitationPayload) => void;
  onRegenerate?: () => void;
  onRegenerateSameSources?: () => void;
  onRetryFreshRetrieval?: () => void;
}

export function MessageItem({
  message,
  workspaceId,
  onCitationClick,
  onRegenerate,
  onRegenerateSameSources,
  onRetryFreshRetrieval,
}: MessageItemProps) {
  const { success } = useToast();
  const [copied, setCopied] = useState(false);
  const [userRating, setUserRating] = useState<"up" | "down" | null>(null);
  const [feedbackOpen, setFeedbackOpen] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleRating = async (rating: "up" | "down") => {
    if (!workspaceId) return;
    setUserRating(rating);
    try {
      await api.submitFeedback(workspaceId, message.id, rating);
      success("Feedback Recorded", "Thank you for rating this response.");
    } catch {
      // ignore
    }
  };

  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex gap-3.5 sm:gap-4 p-4 sm:p-5 rounded-2xl transition-all",
        isUser
          ? "bg-slate-900/60 border border-slate-800/80 ml-auto max-w-2xl"
          : "bg-slate-900/40 border border-slate-800/60 shadow-lg"
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "w-8 h-8 rounded-xl flex items-center justify-center shrink-0 text-white font-bold text-xs shadow-md",
          isUser
            ? "bg-slate-800 border border-slate-700"
            : "bg-gradient-to-tr from-sky-500 to-indigo-600 shadow-sky-500/20"
        )}
      >
        {isUser ? <User className="w-4 h-4 text-slate-300" /> : <Sparkles className="w-4 h-4" />}
      </div>

      {/* Content Body */}
      <div className="flex-1 overflow-hidden space-y-2">
        {/* Header line */}
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-slate-300">
            {isUser ? "You" : "TitanRAG Assistant"}
          </span>

          {!isUser && message.verified && (
            <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-[10px] font-semibold">
              <CheckCircle2 className="w-3 h-3" />
              <span>
                NLI Verified {message.entailmentScore ? `(${(message.entailmentScore * 100).toFixed(0)}%)` : ""}
              </span>
            </div>
          )}
        </div>

        {/* Markdown Content */}
        {isUser ? (
          <p className="text-sm text-slate-200 whitespace-pre-wrap leading-relaxed">
            {message.content}
          </p>
        ) : (
          <MarkdownRenderer
            content={message.content}
            citations={message.citations}
            onCitationClick={onCitationClick}
          />
        )}

        {/* Citations Tray */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <CitationCardTray
            citations={message.citations}
            onCitationClick={onCitationClick}
          />
        )}

        {/* Assistant Footer: Stats & Actions */}
        {!isUser && message.content && (
          <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 text-[11px] text-slate-500">
            <div className="flex items-center gap-3">
              {message.latencyMs !== undefined && message.latencyMs > 0 && (
                <span className="flex items-center gap-1 font-mono">
                  <Clock className="w-3 h-3" />
                  <span>{(message.latencyMs / 1000).toFixed(2)}s</span>
                </span>
              )}
              {message.tokensUsed !== undefined && message.tokensUsed > 0 && (
                <span className="flex items-center gap-1 font-mono">
                  <Zap className="w-3 h-3 text-amber-400" />
                  <span>{message.tokensUsed} tokens</span>
                </span>
              )}
              {message.cached && (
                <span className="text-emerald-400 font-semibold uppercase text-[10px] px-1.5 py-0.2 rounded bg-emerald-500/10 border border-emerald-500/20">
                  Cached
                </span>
              )}
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={handleCopy}
                className="p-1.5 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-slate-800 transition-colors"
                title="Copy response"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>

              <button
                onClick={() => handleRating("up")}
                className={cn(
                  "p-1.5 rounded-lg transition-colors",
                  userRating === "up"
                    ? "text-emerald-400 bg-emerald-500/10"
                    : "text-slate-500 hover:text-slate-300 hover:bg-slate-800"
                )}
                title="Helpful response"
              >
                <ThumbsUp className="w-3.5 h-3.5" />
              </button>

              <button
                onClick={() => {
                  handleRating("down");
                  setFeedbackOpen(true);
                }}
                className={cn(
                  "p-1.5 rounded-lg transition-colors",
                  userRating === "down"
                    ? "text-rose-400 bg-rose-500/10"
                    : "text-slate-500 hover:text-slate-300 hover:bg-slate-800"
                )}
                title="Report issue or ungrounded claim"
              >
                <ThumbsDown className="w-3.5 h-3.5" />
              </button>

              <RegenerateDropdown
                onRegenerateSameSources={onRegenerateSameSources || onRegenerate || (() => {})}
                onRetryFreshRetrieval={onRetryFreshRetrieval || onRegenerate || (() => {})}
              />
            </div>
          </div>
        )}
      </div>

      {/* Feedback Reporting Modal */}
      <FeedbackModal
        isOpen={feedbackOpen}
        onClose={() => setFeedbackOpen(false)}
        workspaceId={workspaceId}
        messageId={message.id}
      />
    </div>
  );
}
