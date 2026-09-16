"use client";

import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { slideInRight } from "@/lib/animations";
import { RAGSettingsRecord, api } from "@/lib/api";
import { Tabs } from "@/components/ui/Tabs";
import { Slider } from "@/components/ui/Slider";
import { Toggle } from "@/components/ui/Toggle";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import {
  X,
  Sliders,
  Search,
  Brain,
  Shield,
  Zap,
  CheckCircle2,
  RefreshCw,
  Sparkles,
} from "lucide-react";

export interface RagSettingsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  workspaceId: string | undefined;
}

export function RagSettingsDrawer({
  isOpen,
  onClose,
  workspaceId,
}: RagSettingsDrawerProps) {
  const { success, error } = useToast();

  const [activeTab, setActiveTab] = useState<"search" | "generation" | "guardrails" | "cache">("search");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const [settings, setSettings] = useState<RAGSettingsRecord>({
    workspace_id: workspaceId || "",
    search_strategy: "hybrid",
    hybrid_alpha: 0.7,
    top_k: 40,
    rerank_top_k: 5,
    reranker_model: "cohere-rerank-v3",
    score_threshold: 0.4,
    llm_model: "gpt-4o",
    grounding_mode: "balanced",
    system_prompt:
      "You are TitanRAG, an enterprise AI assistant. Answer using strictly the verified sources provided in the context.",
    temperature: 0.2,
    parent_context_enabled: true,
    hyde_enabled: false,
    contextual_chunking_enabled: true,
    nli_verification_enabled: true,
    pii_redaction_mode: "REPLACE",
    semantic_cache_enabled: true,
    cache_similarity_threshold: 0.95,
    cache_ttl_seconds: 86400,
  });

  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch current workspace settings on open
  useEffect(() => {
    if (!isOpen || !workspaceId) return;

    setLoading(true);
    api
      .getRagSettings(workspaceId)
      .then((res) => {
        setSettings(res);
      })
      .catch((err) => {
        console.warn("Could not load RAG settings, using defaults:", err.message);
      })
      .finally(() => setLoading(false));
  }, [isOpen, workspaceId]);

  // Handle Esc key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Debounced auto-save function (500ms)
  const handleSettingChange = <K extends keyof RAGSettingsRecord>(
    key: K,
    value: RAGSettingsRecord[K]
  ) => {
    const updated = { ...settings, [key]: value };
    setSettings(updated);

    if (!workspaceId) return;

    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(async () => {
      setSaving(true);
      try {
        await api.updateRagSettings(workspaceId, updated);
        success("Auto-Saved", "RAG parameter changes applied to live pipeline.");
      } catch (err: any) {
        error("Auto-save failed", err.message);
      } finally {
        setSaving(false);
      }
    }, 500);
  };

  const tabs = [
    { id: "search" as const, label: "Search & Rerank", icon: <Search className="w-3.5 h-3.5" /> },
    { id: "generation" as const, label: "Generation", icon: <Brain className="w-3.5 h-3.5" /> },
    { id: "guardrails" as const, label: "Guardrails", icon: <Shield className="w-3.5 h-3.5" /> },
    { id: "cache" as const, label: "Cache & Latency", icon: <Zap className="w-3.5 h-3.5" /> },
  ];

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          variants={slideInRight}
          initial="hidden"
          animate="visible"
          exit="exit"
          className="fixed top-0 right-0 h-screen w-full sm:w-[480px] md:w-[560px] bg-slate-950/95 border-l border-slate-800 shadow-2xl z-50 flex flex-col backdrop-blur-2xl"
        >
          {/* Header */}
          <div className="h-14 border-b border-slate-800/80 px-5 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2">
              <Sliders className="w-4 h-4 text-sky-400" />
              <h3 className="text-sm font-bold text-white tracking-tight">RAG Tuning & Guardrails</h3>
            </div>
            <div className="flex items-center gap-2">
              {saving && (
                <span className="text-[11px] text-sky-400 flex items-center gap-1">
                  <RefreshCw className="w-3 h-3 animate-spin" />
                  <span>Saving...</span>
                </span>
              )}
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-900 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Tab navigation */}
          <div className="px-5 pt-3 border-b border-slate-800/60">
            <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} variant="underline" />
          </div>

          {/* Drawer Body */}
          <div className="flex-1 overflow-y-auto p-5 space-y-6">
            {/* Search & Reranking Tab */}
            {activeTab === "search" && (
              <div className="space-y-5">
                {/* Search Strategy Radio */}
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-slate-200">Retrieval Strategy</label>
                  <div className="grid grid-cols-3 gap-2">
                    {(["hybrid", "dense", "sparse"] as const).map((strategy) => (
                      <button
                        key={strategy}
                        type="button"
                        onClick={() => handleSettingChange("search_strategy", strategy)}
                        className={`p-2.5 rounded-xl border text-xs font-bold capitalize transition-all ${
                          settings.search_strategy === strategy
                            ? "bg-sky-500/15 border-sky-500 text-sky-400"
                            : "bg-slate-900/60 border-slate-800 text-slate-400 hover:text-white"
                        }`}
                      >
                        {strategy}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Hybrid Alpha Slider */}
                {settings.search_strategy === "hybrid" && (
                  <Slider
                    label="Hybrid Alpha (Keyword ↔ Semantic Balance)"
                    min={0}
                    max={1}
                    step={0.05}
                    value={settings.hybrid_alpha}
                    displayValue={`${(settings.hybrid_alpha * 100).toFixed(0)}% Dense`}
                    onChange={(val) => handleSettingChange("hybrid_alpha", val)}
                  />
                )}

                {/* Top K retrieval */}
                <Slider
                  label="Candidate Retrieval Depth (Top K)"
                  min={10}
                  max={100}
                  step={5}
                  value={settings.top_k}
                  displayValue={`${settings.top_k} chunks`}
                  onChange={(val) => handleSettingChange("top_k", val)}
                />

                {/* Reranker Model */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-200">Cross-Encoder Reranker</label>
                  <select
                    value={settings.reranker_model}
                    onChange={(e) => handleSettingChange("reranker_model", e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                  >
                    <option value="cohere-rerank-v3">Cohere Rerank v3 (Cloud API)</option>
                    <option value="bge-reranker-large">BGE Reranker Large (Self-Hosted GPU)</option>
                    <option value="none">None (Reciprocal Rank Fusion Only)</option>
                  </select>
                </div>

                {/* Rerank N output depth */}
                <Slider
                  label="Context Assembly Window (Rerank Top N)"
                  min={3}
                  max={20}
                  step={1}
                  value={settings.rerank_top_k}
                  displayValue={`${settings.rerank_top_k} passages`}
                  onChange={(val) => handleSettingChange("rerank_top_k", val)}
                />

                {/* CRAG Confidence Rejection Gate */}
                <Slider
                  label="CRAG Confidence Rejection Threshold"
                  min={0.1}
                  max={0.9}
                  step={0.05}
                  value={settings.score_threshold}
                  displayValue={settings.score_threshold.toFixed(2)}
                  onChange={(val) => handleSettingChange("score_threshold", val)}
                />
              </div>
            )}

            {/* Generation Tab */}
            {activeTab === "generation" && (
              <div className="space-y-5">
                {/* Model Override */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-200">LLM Generation Model</label>
                  <select
                    value={settings.llm_model}
                    onChange={(e) => handleSettingChange("llm_model", e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                  >
                    <option value="gpt-4o">OpenAI GPT-4o (Default)</option>
                    <option value="claude-3-5-sonnet">Anthropic Claude 3.5 Sonnet</option>
                    <option value="llama-3-3-70b">Meta Llama 3.3 70B Instruct</option>
                    <option value="gemini-1-5-pro">Google Gemini 1.5 Pro</option>
                  </select>
                </div>

                {/* Grounding Mode */}
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-slate-200">Grounding Strictness</label>
                  <div className="grid grid-cols-3 gap-2">
                    {(["strict", "balanced", "creative"] as const).map((mode) => (
                      <button
                        key={mode}
                        type="button"
                        onClick={() => handleSettingChange("grounding_mode", mode)}
                        className={`p-2.5 rounded-xl border text-xs font-bold capitalize transition-all ${
                          settings.grounding_mode === mode
                            ? "bg-sky-500/15 border-sky-500 text-sky-400"
                            : "bg-slate-900/60 border-slate-800 text-slate-400 hover:text-white"
                        }`}
                      >
                        {mode}
                      </button>
                    ))}
                  </div>
                </div>

                {/* System Prompt */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-200">System Instruction Prompt</label>
                  <textarea
                    rows={4}
                    value={settings.system_prompt || ""}
                    onChange={(e) => handleSettingChange("system_prompt", e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-500 leading-relaxed resize-none"
                  />
                </div>

                {/* Temperature */}
                <Slider
                  label="Sampling Temperature"
                  min={0.0}
                  max={1.0}
                  step={0.05}
                  value={settings.temperature}
                  displayValue={settings.temperature.toFixed(2)}
                  onChange={(val) => handleSettingChange("temperature", val)}
                />

                {/* HyDE Toggle */}
                <Toggle
                  checked={settings.hyde_enabled}
                  onChange={(checked) => handleSettingChange("hyde_enabled", checked)}
                  label="HyDE (Hypothetical Document Embeddings)"
                  description="Generate hypothetical answers before vector search to boost recall on abstract questions."
                />

                {/* Parent Context Toggle */}
                <Toggle
                  checked={settings.parent_context_enabled}
                  onChange={(checked) => handleSettingChange("parent_context_enabled", checked)}
                  label="Parent Chunk Context Injection"
                  description="Inject full parent section (1024 tok) for child passages during synthesis."
                />
              </div>
            )}

            {/* Guardrails Tab */}
            {activeTab === "guardrails" && (
              <div className="space-y-5">
                <Toggle
                  checked={settings.nli_verification_enabled}
                  onChange={(checked) => handleSettingChange("nli_verification_enabled", checked)}
                  label="NLI Claim Entailment Verification"
                  description="Async Natural Language Inference verification on generated claims against cited source chunks."
                />

                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-200">PII Redaction Mode</label>
                  <select
                    value={settings.pii_redaction_mode}
                    onChange={(e) => handleSettingChange("pii_redaction_mode", e.target.value as any)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                  >
                    <option value="REPLACE">REPLACE (e.g. [PERSON], [EMAIL])</option>
                    <option value="MASK">MASK (e.g. J*** D**)</option>
                    <option value="HASH">HASH (SHA-256 Digest)</option>
                    <option value="OFF">OFF (Do Not Redact)</option>
                  </select>
                </div>
              </div>
            )}

            {/* Cache Tab */}
            {activeTab === "cache" && (
              <div className="space-y-5">
                <Toggle
                  checked={settings.semantic_cache_enabled}
                  onChange={(checked) => handleSettingChange("semantic_cache_enabled", checked)}
                  label="Redis Semantic Query Cache"
                  description="Return sub-200ms responses for semantically identical queries within the workspace."
                />

                {settings.semantic_cache_enabled && (
                  <>
                    <Slider
                      label="Cache Similarity Threshold (Cosine)"
                      min={0.85}
                      max={0.99}
                      step={0.01}
                      value={settings.cache_similarity_threshold}
                      displayValue={settings.cache_similarity_threshold.toFixed(2)}
                      onChange={(val) => handleSettingChange("cache_similarity_threshold", val)}
                    />

                    <Input
                      label="Cache TTL (Seconds)"
                      type="number"
                      value={settings.cache_ttl_seconds}
                      onChange={(e) => handleSettingChange("cache_ttl_seconds", parseInt(e.target.value) || 86400)}
                    />
                  </>
                )}
              </div>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
