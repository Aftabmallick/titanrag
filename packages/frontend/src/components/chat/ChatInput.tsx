"use client";

import React, { useRef, useEffect } from "react";
import { ArrowUp, Square, Paperclip } from "lucide-react";
import { StreamStatus } from "@/hooks/useChatStream";

export interface ChatInputProps {
  query: string;
  setQuery: (q: string) => void;
  onSend: () => void;
  onStop: () => void;
  status: StreamStatus;
  disabled?: boolean;
}

export function ChatInput({
  query,
  setQuery,
  onSend,
  onStop,
  status,
  disabled = false,
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const isStreaming = status === "retrieving" || status === "streaming";

  // Auto-resize textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        180
      )}px`;
    }
  }, [query]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isStreaming && query.trim()) {
        onSend();
      }
    }
  };

  return (
    <div className="relative rounded-2xl border border-slate-800 bg-slate-900/90 shadow-2xl p-2.5 focus-within:border-sky-500/80 focus-within:ring-2 focus-within:ring-sky-500/20 transition-all">
      <textarea
        ref={textareaRef}
        rows={1}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask a question across your workspace documents (Enter to send, Shift + Enter for new line)..."
        disabled={disabled}
        className="w-full bg-transparent text-sm text-slate-100 placeholder-slate-500 focus:outline-none resize-none px-2 py-1 max-h-[180px] leading-relaxed disabled:opacity-50"
      />

      <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 mt-1">
        <div className="flex items-center gap-1">
          <button
            type="button"
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-slate-800 transition-colors"
            title="Attach file (optional)"
          >
            <Paperclip className="w-4 h-4" />
          </button>
          <span className="text-[11px] text-slate-500 hidden sm:inline">
            Press <kbd className="font-mono bg-slate-800 px-1 py-0.5 rounded text-[10px]">↵ Enter</kbd> to send
          </span>
        </div>

        <div>
          {isStreaming ? (
            <button
              type="button"
              onClick={onStop}
              id="chat-stop-btn"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow-md shadow-rose-600/20 transition-all cursor-pointer"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
              <span>Stop</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={onSend}
              id="chat-send-btn"
              disabled={!query.trim() || disabled}
              className="p-2 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white disabled:opacity-40 disabled:pointer-events-none transition-all cursor-pointer shadow-md shadow-sky-500/20"
            >
              <ArrowUp className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
