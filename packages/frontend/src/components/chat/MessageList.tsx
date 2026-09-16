"use client";

import React, { useRef, useEffect, useState } from "react";
import { ChatMessage, StreamStatus } from "@/hooks/useChatStream";
import { CitationPayload } from "@/lib/api";
import { MessageItem } from "./MessageItem";
import { FollowUpSuggestions } from "./FollowUpSuggestions";
import { ArrowDown, Loader2, Sparkles } from "lucide-react";

export interface MessageListProps {
  messages: ChatMessage[];
  status: StreamStatus;
  retrievalStatusMessage: string | null;
  suggestions: string[];
  workspaceId?: string;
  onCitationClick: (citation: CitationPayload) => void;
  onSelectSuggestion: (query: string) => void;
  onRegenerateLast?: () => void;
}

export function MessageList({
  messages,
  status,
  retrievalStatusMessage,
  suggestions,
  workspaceId,
  onCitationClick,
  onSelectSuggestion,
  onRegenerateLast,
}: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [showScrollBottom, setShowScrollBottom] = useState(false);
  const userScrolledUpRef = useRef(false);

  // Monitor user scroll position
  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const distanceToBottom = scrollHeight - (scrollTop + clientHeight);

    if (distanceToBottom > 60) {
      userScrolledUpRef.current = true;
      setShowScrollBottom(true);
    } else {
      userScrolledUpRef.current = false;
      setShowScrollBottom(false);
    }
  };

  // Auto-scroll when messages update, unless user scrolled up
  useEffect(() => {
    if (!userScrolledUpRef.current && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [messages, retrievalStatusMessage]);

  const scrollToBottom = () => {
    if (containerRef.current) {
      containerRef.current.scrollTo({
        top: containerRef.current.scrollHeight,
        behavior: "smooth",
      });
      userScrolledUpRef.current = false;
      setShowScrollBottom(false);
    }
  };

  return (
    <div className="relative flex-1 overflow-hidden">
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="h-full overflow-y-auto px-4 sm:px-8 py-6 space-y-5"
      >
        {messages.map((msg, idx) => (
          <MessageItem
            key={msg.id || idx}
            message={msg}
            workspaceId={workspaceId}
            onCitationClick={onCitationClick}
            onRegenerate={idx === messages.length - 1 && msg.role === "assistant" ? onRegenerateLast : undefined}
          />
        ))}

        {/* Phase 1 & 2 Retrieval Status Banner */}
        {retrievalStatusMessage && (
          <div className="flex items-center gap-3 p-3.5 rounded-2xl border border-sky-500/20 bg-sky-950/20 backdrop-blur-md text-xs text-sky-300 animate-pulse">
            <Loader2 className="w-4 h-4 animate-spin text-sky-400 shrink-0" />
            <span className="font-medium tracking-wide">{retrievalStatusMessage}</span>
          </div>
        )}

        {/* Suggested Follow-Ups */}
        {suggestions.length > 0 && status === "done" && (
          <FollowUpSuggestions
            suggestions={suggestions}
            onSelectSuggestion={onSelectSuggestion}
          />
        )}
      </div>

      {/* Floating Scroll to Bottom Button */}
      {showScrollBottom && (
        <button
          onClick={scrollToBottom}
          className="absolute bottom-4 right-8 flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-800/90 border border-slate-700 shadow-xl text-xs font-semibold text-sky-400 hover:text-white hover:bg-slate-700 transition-all cursor-pointer backdrop-blur-md"
        >
          <ArrowDown className="w-3.5 h-3.5" />
          <span>New tokens below</span>
          <span className="w-2 h-2 rounded-full bg-sky-400 animate-ping" />
        </button>
      )}
    </div>
  );
}
