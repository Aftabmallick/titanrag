"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { slideInRight } from "@/lib/animations";
import { useRagSettings } from "@/hooks/useRagSettings";
import { Tabs } from "@/components/ui/Tabs";
import {
  X,
  Sliders,
  Search,
  Brain,
  Shield,
  Zap,
  RefreshCw,
} from "lucide-react";
import { SearchRetrievalTab } from "./SearchRetrievalTab";
import { GenerationLlmTab } from "./GenerationLlmTab";
import { GuardrailsPrivacyTab } from "./GuardrailsPrivacyTab";
import { SemanticCacheTab } from "./SemanticCacheTab";

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
  const [activeTab, setActiveTab] = useState<"search" | "generation" | "guardrails" | "cache">("search");
  const { settings, saving, loading, updateSetting, resetToDefaults } = useRagSettings(workspaceId);

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
                <span className="text-[11px] text-sky-400 flex items-center gap-1 font-medium">
                  <RefreshCw className="w-3 h-3 animate-spin" />
                  <span>Auto-Saving...</span>
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
            {loading || !settings ? (
              <div className="py-20 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin text-sky-400" />
                <span>Loading workspace configuration...</span>
              </div>
            ) : (
              <>
                {activeTab === "search" && (
                  <SearchRetrievalTab settings={settings} onChange={updateSetting} />
                )}
                {activeTab === "generation" && (
                  <GenerationLlmTab settings={settings} onChange={updateSetting} />
                )}
                {activeTab === "guardrails" && (
                  <GuardrailsPrivacyTab settings={settings} onChange={updateSetting} />
                )}
                {activeTab === "cache" && (
                  <SemanticCacheTab settings={settings} onChange={updateSetting} />
                )}
              </>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
