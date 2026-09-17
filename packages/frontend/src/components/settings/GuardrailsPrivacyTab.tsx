"use client";

import React from "react";
import { Toggle } from "@/components/ui/Toggle";
import { RAGSettingsRecord } from "@/lib/api";

export interface GuardrailsPrivacyTabProps {
  settings: RAGSettingsRecord;
  onChange: <K extends keyof RAGSettingsRecord>(key: K, value: RAGSettingsRecord[K]) => void;
}

export function GuardrailsPrivacyTab({ settings, onChange }: GuardrailsPrivacyTabProps) {
  const piiMode = settings?.pii_redaction_mode || "REPLACE";
  const nliVerificationEnabled = Boolean(settings?.nli_verification_enabled);
  const contextualChunkingEnabled = Boolean(settings?.contextual_chunking_enabled);

  return (
    <div className="space-y-6">
      {/* PII Redaction Mode */}
      <div className="space-y-2">
        <label className="text-xs font-semibold text-slate-300">PII Redaction Mode</label>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {([
            { id: "REPLACE" as const, label: "Entity Replace", desc: "[EMAIL], [SSN]" },
            { id: "MASK" as const, label: "Partial Mask", desc: "J*** D**" },
            { id: "HASH" as const, label: "Salted Hash", desc: "sha256[:8]" },
            { id: "OFF" as const, label: "Disabled", desc: "No Redaction" },
          ]).map((mode) => (
            <button
              key={mode.id}
              type="button"
              onClick={() => onChange("pii_redaction_mode", mode.id)}
              className={`p-3 text-left rounded-lg border transition-all ${
                piiMode === mode.id
                  ? "bg-rose-500/20 border-rose-500 text-white shadow-sm"
                  : "bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200"
              }`}
            >
              <div className="text-xs font-bold text-slate-200">{mode.label}</div>
              <div className="text-[10px] text-slate-500 mt-0.5">{mode.desc}</div>
            </button>
          ))}
        </div>
      </div>

      {/* NLI Claim Verification */}
      <div className="space-y-3 pt-2 border-t border-slate-800">
        <Toggle
          label="NLI Natural Language Inference Verification"
          description="Runs async entailment audit verifying that assistant assertions are strictly grounded in retrieved citations"
          checked={nliVerificationEnabled}
          onChange={(val) => onChange("nli_verification_enabled", val)}
        />
        <Toggle
          label="Contextual Chunking Enrichment"
          description="Prepends document summary and section headers to each chunk before embedding"
          checked={contextualChunkingEnabled}
          onChange={(val) => onChange("contextual_chunking_enabled", val)}
        />
      </div>
    </div>
  );
}
