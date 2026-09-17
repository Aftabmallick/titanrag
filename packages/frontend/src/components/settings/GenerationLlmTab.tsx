"use client";

import React from "react";
import { Slider } from "@/components/ui/Slider";
import { RAGSettingsRecord } from "@/lib/api";

export interface GenerationLlmTabProps {
  settings: RAGSettingsRecord;
  onChange: <K extends keyof RAGSettingsRecord>(key: K, value: RAGSettingsRecord[K]) => void;
}

export function GenerationLlmTab({ settings, onChange }: GenerationLlmTabProps) {
  const temperature = typeof settings?.temperature === "number" ? settings.temperature : 0.2;
  const llmModel = settings?.llm_model || "gpt-4o";
  const systemPrompt = settings?.system_prompt ?? "";

  return (
    <div className="space-y-6">
      {/* Model Selection */}
      <div className="space-y-2">
        <label className="text-xs font-semibold text-slate-300">Foundation LLM Model</label>
        <div className="grid grid-cols-2 gap-2">
          {[
            { id: "gpt-4o", label: "GPT-4o (Default)", provider: "OpenAI" },
            { id: "claude-3-5-sonnet-20241022", label: "Claude 3.5 Sonnet", provider: "Anthropic" },
            { id: "deepseek-ai/deepseek-v4-flash-0731", label: "DeepSeek V4 Flash", provider: "NVIDIA NIM" },
            { id: "meta-llama/llama-3.1-70b-instruct", label: "Llama 3.1 70B", provider: "Meta / Groq" },
          ].map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => onChange("llm_model", m.id)}
              className={`p-3 text-left rounded-lg border transition-all ${
                llmModel === m.id
                  ? "bg-indigo-500/20 border-indigo-500 text-white shadow-sm"
                  : "bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200"
              }`}
            >
              <div className="text-xs font-bold text-slate-200">{m.label}</div>
              <div className="text-[10px] text-slate-500 mt-0.5 font-mono">{m.provider}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Temperature */}
      <div className="space-y-2">
        <div className="flex justify-between items-center text-xs">
          <span className="font-semibold text-slate-300">Generation Temperature</span>
          <span className="font-mono text-indigo-400">{temperature.toFixed(2)}</span>
        </div>
        <Slider
          min={0.0}
          max={1.0}
          step={0.05}
          value={temperature}
          onChange={(val) => onChange("temperature", val)}
        />
        <div className="flex justify-between text-[10px] text-slate-400">
          <span>0.0 (Strict / Deterministic)</span>
          <span>0.7 (Creative)</span>
        </div>
      </div>

      {/* System Prompt Override */}
      <div className="space-y-2">
        <label className="text-xs font-semibold text-slate-300">System Prompt</label>
        <textarea
          rows={5}
          value={systemPrompt}
          onChange={(e) => onChange("system_prompt", e.target.value)}
          className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 font-mono leading-relaxed"
          placeholder="System prompt template..."
        />
        <p className="text-[11px] text-slate-500">
          Instructions given to the LLM. Use {"{context}"} and {"{query}"} for variable interpolation.
        </p>
      </div>
    </div>
  );
}
