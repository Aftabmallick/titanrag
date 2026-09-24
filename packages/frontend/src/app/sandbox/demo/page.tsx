"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  Send,
  Sparkles,
  FileText,
  Clock,
  Shield,
  Layers,
  CheckCircle,
  Sliders,
  ChevronRight,
  ExternalLink,
} from "lucide-react";
import { DemoGuidedTour } from "@/components/sandbox/DemoGuidedTour";

interface Citation {
  source: string;
  page: number;
  text: string;
  score: number;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  latency_ms?: number;
  faithfulness?: number;
}

const PRELOADED_DOCS = [
  { title: "Master Services Agreement (MSA)", type: "Legal", pages: 28, status: "Indexed" },
  { title: "Distributed Consensus & Vector RAG Architecture", type: "Technical", pages: 42, status: "Indexed" },
  { title: "Q2 2026 Earnings & Financial Performance", type: "Finance", pages: 18, status: "Indexed" },
];

export default function SandboxDemoPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "initial-assistant",
      role: "assistant",
      content:
        "Welcome to the TitanRAG Hosted Sandbox! I have indexed 3 demo documents covering Legal, Architecture, and Financial disclosures. Ask any question to test our hybrid vector + sparse retrieval and citation accuracy.",
    },
  ]);
  const [inputQuery, setInputQuery] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);

  const handleSend = () => {
    if (!inputQuery.trim() || isGenerating) return;

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: inputQuery,
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputQuery("");
    setIsGenerating(true);

    setTimeout(() => {
      const assistantMsg: Message = {
        id: `asst-${Date.now()}`,
        role: "assistant",
        content:
          "According to Section 14.2 of the Master Services Agreement, either party may terminate the agreement upon thirty (30) days' written notice in the event of an uncured material breach. Furthermore, liability under breach of confidentiality is explicitly exempted from the standard aggregate liability cap of twelve (12) months of fees paid.",
        latency_ms: 284,
        faithfulness: 0.992,
        citations: [
          {
            source: "Master Services Agreement (MSA)",
            page: 14,
            text: "Section 14.2 Termination for Cause: Either Party may terminate this Agreement immediately upon written notice if the other Party materially breaches any term...",
            score: 0.96,
          },
          {
            source: "Master Services Agreement (MSA)",
            page: 19,
            text: "Section 17.4 Exclusions from Limitation of Liability: The limitations set forth in Section 17.1 shall not apply to breaches of Section 11 (Confidentiality)...",
            score: 0.91,
          },
        ],
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setIsGenerating(false);
    }, 600);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Interactive Tour Modal */}
      <DemoGuidedTour />

      {/* Top Banner: Ephemeral Session Notice */}
      <div className="bg-indigo-950/40 border-b border-indigo-900/40 px-6 py-2.5 flex items-center justify-between text-xs">
        <div className="flex items-center gap-2 text-indigo-300">
          <Clock className="w-4 h-4 text-indigo-400" />
          <span>
            <strong>Ephemeral Sandbox Session:</strong> Isolated workspace valid for 24 hours. Rate limited to 10 queries/hour.
          </span>
        </div>
        <Link
          href="/admin/billing"
          className="font-medium text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
        >
          <span>Upgrade to Pro</span>
          <ChevronRight className="w-3.5 h-3.5" />
        </Link>
      </div>

      {/* Main Workspace Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar: Preloaded Documents */}
        <aside className="w-80 border-r border-slate-800/80 bg-slate-900/40 p-5 hidden md:flex flex-col gap-6">
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
              <FileText className="w-4 h-4 text-indigo-400" />
              Preloaded Golden Dataset
            </h2>
            <div className="space-y-2.5">
              {PRELOADED_DOCS.map((doc) => (
                <div
                  key={doc.title}
                  className="p-3 rounded-xl border border-slate-800 bg-slate-900/80 text-xs space-y-1.5"
                >
                  <div className="font-medium text-slate-200 line-clamp-1">{doc.title}</div>
                  <div className="flex items-center justify-between text-slate-400">
                    <span>{doc.type} &bull; {doc.pages} pgs</span>
                    <span className="text-emerald-400 flex items-center gap-1 font-mono text-[11px]">
                      <CheckCircle className="w-3 h-3" />
                      {doc.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/60 text-xs space-y-2 text-slate-400 mt-auto">
            <div className="font-semibold text-slate-300 flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5 text-indigo-400" />
              Security Sandbox Mode
            </div>
            <p>
              Air-gapped Kubernetes pod namespace with NetworkPolicy isolation and automatic purge.
            </p>
          </div>
        </aside>

        {/* Center Chat Area */}
        <main className="flex-1 flex flex-col bg-slate-950 overflow-hidden">
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`flex gap-4 max-w-3xl ${
                  m.role === "user" ? "ml-auto justify-end" : ""
                }`}
              >
                {m.role === "assistant" && (
                  <div className="w-8 h-8 rounded-lg bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center text-indigo-300 shrink-0">
                    <Sparkles className="w-4 h-4" />
                  </div>
                )}

                <div
                  className={`space-y-3 rounded-2xl p-4 text-sm leading-relaxed ${
                    m.role === "user"
                      ? "bg-indigo-600 text-white"
                      : "bg-slate-900/90 border border-slate-800 text-slate-200"
                  }`}
                >
                  <p>{m.content}</p>

                  {/* Metadata and Citations for Assistant */}
                  {m.citations && (
                    <div className="pt-2 border-t border-slate-800/80 space-y-2">
                      <div className="flex items-center gap-3 text-xs text-slate-400">
                        {m.latency_ms && (
                          <span>TTFT: <strong>{m.latency_ms}ms</strong></span>
                        )}
                        {m.faithfulness && (
                          <span className="text-emerald-400">
                            Faithfulness: <strong>{(m.faithfulness * 100).toFixed(1)}%</strong>
                          </span>
                        )}
                      </div>

                      <div className="flex flex-wrap gap-2">
                        {m.citations.map((c, i) => (
                          <button
                            key={i}
                            onClick={() => setSelectedCitation(c)}
                            className="px-2.5 py-1 rounded-md bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 text-xs text-indigo-300 flex items-center gap-1.5 transition-colors"
                          >
                            <FileText className="w-3 h-3" />
                            <span>{c.source} (p. {c.page})</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {isGenerating && (
              <div className="flex gap-4 max-w-3xl">
                <div className="w-8 h-8 rounded-lg bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center text-indigo-300 shrink-0 animate-pulse">
                  <Sparkles className="w-4 h-4" />
                </div>
                <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 text-xs text-slate-400 flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-indigo-400 animate-ping" />
                  <span>Searching Qdrant vectors + BM25 sparse index...</span>
                </div>
              </div>
            )}
          </div>

          {/* Chat Input */}
          <div className="p-4 border-t border-slate-800 bg-slate-950/80">
            <div className="max-w-3xl mx-auto flex items-center gap-2">
              <input
                type="text"
                placeholder="Ask anything about the demo documents..."
                value={inputQuery}
                onChange={(e) => setInputQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSend()}
                className="flex-1 bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <button
                onClick={handleSend}
                disabled={!inputQuery.trim() || isGenerating}
                className="p-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl shadow-lg shadow-indigo-600/30 transition-all"
                aria-label="Send query"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </main>

        {/* Right Drawer: Citation Inspector (if selected) */}
        {selectedCitation && (
          <aside className="w-80 border-l border-slate-800/80 bg-slate-900/50 p-5 flex flex-col gap-4 animate-in slide-in-from-right">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Ground-Truth Citation
              </h3>
              <button
                onClick={() => setSelectedCitation(null)}
                className="text-xs text-slate-400 hover:text-slate-200"
              >
                Close
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <div className="text-slate-400">Document:</div>
                <div className="font-semibold text-slate-200">{selectedCitation.source}</div>
              </div>

              <div>
                <div className="text-slate-400">Page:</div>
                <div className="font-semibold text-slate-200">{selectedCitation.page}</div>
              </div>

              <div>
                <div className="text-slate-400">Retrieval Relevance Score:</div>
                <div className="font-semibold text-indigo-400">
                  {(selectedCitation.score * 100).toFixed(1)}%
                </div>
              </div>

              <div>
                <div className="text-slate-400 mb-1">Extracted Text Chunk:</div>
                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-slate-300 italic leading-relaxed">
                  &ldquo;{selectedCitation.text}&rdquo;
                </div>
              </div>
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
