"use client";

import React, { useState } from "react";
import { useChatStream } from "@/hooks/useChatStream";
import { MessageList } from "./MessageList";
import { ChatControlsBar } from "./ChatControlsBar";
import { ChatInput } from "./ChatInput";
import { CitationPayload } from "@/lib/api";
import { EmptyState } from "@/components/ui/EmptyState";
import { Sparkles, FileText, Zap, ShieldCheck, Download, Printer, FileCode } from "lucide-react";
import { exportChatMarkdown, exportChatPrintPdf, exportChatJson } from "@/lib/export-chat";

export interface ChatContainerProps {
  workspaceId: string | undefined;
  sessionId?: string | null;
  sessionTitle?: string;
  onCitationClick: (citation: CitationPayload) => void;
  onOpenSettingsDrawer?: () => void;
}

export function ChatContainer({
  workspaceId,
  sessionId,
  sessionTitle = "Chat Session",
  onCitationClick,
  onOpenSettingsDrawer,
}: ChatContainerProps) {
  const {
    messages,
    status,
    retrievalStatusMessage,
    suggestions,
    error,
    sendQuery,
    abort,
  } = useChatStream(workspaceId);

  const [query, setQuery] = useState("");
  const [pipelineMode, setPipelineMode] = useState<"auto" | "fast" | "deep">("auto");
  const [groundingMode, setGroundingMode] = useState<"strict" | "balanced" | "creative">("balanced");
  const [showExportMenu, setShowExportMenu] = useState(false);

  const handleSend = async (textToSend?: string, attachedImageBase64?: string) => {
    let q = textToSend || query;
    if (!q.trim() && !attachedImageBase64) return;

    if (attachedImageBase64) {
      try {
        const res = await fetch("/api/v1/chat/multimodal/query", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_prompt: q || "Explain this diagram or document screenshot",
            image_base64: attachedImageBase64,
          }),
        });
        if (res.ok) {
          const data = await res.json();
          if (data?.data?.search_expansion_query) {
            q = `${q ? q + " " : ""}[Visual Context: ${data.data.visual_summary}]`;
          }
        }
      } catch (err) {
        console.warn("Multimodal query expansion fallback:", err);
      }
    }

    sendQuery(q, {
      sessionId,
      pipelineMode,
      groundingMode,
    });
    setQuery("");
  };

  const exportOpts = {
    messages,
    workspaceId,
    sessionTitle,
    pipelineMode,
    groundingMode,
  };

  const samplePrompts = [
    "What are the key liability limitations in this contract?",
    "Summarize the main financial obligations across our agreements",
    "List all compliance requirements with effective dates",
    "Compare the IP transfer terms between Document A and Document B",
  ];

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)] overflow-hidden bg-slate-950">
      {/* Session Top Bar */}
      <div className="h-11 px-4 sm:px-6 border-b border-slate-800/80 bg-slate-950/60 backdrop-blur-md flex items-center justify-between z-10">
        <div className="flex items-center gap-2.5 overflow-hidden">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <h2 className="text-xs sm:text-sm font-semibold text-slate-200 truncate max-w-xs sm:max-w-sm">
            {sessionTitle}
          </h2>
          <span className="text-[10px] px-2 py-0.5 rounded-md bg-slate-800 text-slate-400 font-mono hidden sm:inline-block">
            {messages.length} messages
          </span>
        </div>

        <div className="flex items-center gap-2">
          {messages.length > 0 && (
            <div className="relative">
              <button
                onClick={() => setShowExportMenu(!showExportMenu)}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-slate-700 bg-slate-900/80 hover:bg-slate-800 text-xs font-medium text-slate-300 hover:text-white transition-all shadow-sm"
                title="Export Transcript"
              >
                <Download className="w-3.5 h-3.5 text-sky-400" />
                <span className="hidden sm:inline">Export</span>
              </button>

              {showExportMenu && (
                <div
                  className="absolute right-0 mt-1.5 w-52 rounded-xl border border-slate-800 bg-slate-900 shadow-2xl p-1.5 z-50 text-xs space-y-1 animate-in fade-in zoom-in-95 duration-100"
                  onMouseLeave={() => setShowExportMenu(false)}
                >
                  <button
                    onClick={() => {
                      exportChatMarkdown(exportOpts);
                      setShowExportMenu(false);
                    }}
                    className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800 transition-colors text-left"
                  >
                    <FileText className="w-3.5 h-3.5 text-sky-400" />
                    <span>Markdown (.md)</span>
                  </button>
                  <button
                    onClick={() => {
                      exportChatPrintPdf(exportOpts);
                      setShowExportMenu(false);
                    }}
                    className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800 transition-colors text-left"
                  >
                    <Printer className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Printable PDF</span>
                  </button>
                  <button
                    onClick={() => {
                      exportChatJson(exportOpts);
                      setShowExportMenu(false);
                    }}
                    className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800 transition-colors text-left"
                  >
                    <FileCode className="w-3.5 h-3.5 text-amber-400" />
                    <span>Structured JSON</span>
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Messages area or Empty State */}
      {messages.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-6 overflow-y-auto">
          <div className="max-w-xl w-full text-center space-y-6">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-sky-500/30 bg-sky-500/10 text-sky-400 text-xs font-semibold uppercase tracking-wider">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Grounded Knowledge Engine</span>
            </div>

            <div className="space-y-2">
              <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                How can TitanRAG assist you?
              </h2>
              <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
                Queries are processed with hybrid dense+sparse retrieval, sub-1.8s Fast-Path routing,
                and post-generation NLI claim verification.
              </p>
            </div>

            {/* Quick Sample Prompts */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-2 text-left">
              {samplePrompts.map((prompt, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSend(prompt)}
                  className="p-3 rounded-xl border border-slate-800 bg-slate-900/50 hover:bg-slate-850 hover:border-slate-700 text-xs text-slate-300 hover:text-white transition-all text-left shadow-sm group cursor-pointer"
                >
                  <span className="line-clamp-2">{prompt}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <MessageList
          messages={messages}
          status={status}
          retrievalStatusMessage={retrievalStatusMessage}
          suggestions={suggestions}
          workspaceId={workspaceId}
          onCitationClick={onCitationClick}
          onSelectSuggestion={(s) => handleSend(s)}
          onRegenerateLast={() => {
            const lastUserMsg = [...messages].reverse().find((m) => m.role === "user");
            if (lastUserMsg) handleSend(lastUserMsg.content);
          }}
        />
      )}

      {/* Error alert if stream failed */}
      {error && (
        <div className="mx-6 mb-2 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-400">
          <strong>Stream Error:</strong> {error}
        </div>
      )}

      {/* Input Dock */}
      <div className="p-4 sm:px-8 border-t border-slate-800/80 bg-slate-950/80 backdrop-blur-xl">
        <div className="max-w-4xl mx-auto space-y-2">
          <ChatControlsBar
            pipelineMode={pipelineMode}
            setPipelineMode={setPipelineMode}
            groundingMode={groundingMode}
            setGroundingMode={setGroundingMode}
            onOpenSettingsDrawer={onOpenSettingsDrawer}
          />
          <ChatInput
            query={query}
            setQuery={setQuery}
            onSend={(img) => handleSend(undefined, img)}
            onStop={abort}
            status={status}
          />
        </div>
      </div>
    </div>
  );
}
