"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Code2,
  Save,
  Rocket,
  RotateCcw,
  CheckCircle2,
  AlertCircle,
  Clock,
  Sparkles,
  Loader2,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";

export function PromptEditorMonaco({ workspaceId }: { workspaceId: string | undefined }) {
  const [slug, setSlug] = useState("system_chat");
  const [content, setContent] = useState(
    `You are TitanRAG, a verified enterprise intelligence assistant.\nAnswer strictly using the verified context below.\n\nContext:\n{{ context }}\n\nQuery:\n{{ query }}`
  );
  const [commitMessage, setCommitMessage] = useState("");
  const [versions, setVersions] = useState<any[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [promoting, setPromoting] = useState(false);

  const fetchVersions = useCallback(async () => {
    if (!workspaceId) return;
    setLoading(true);
    try {
      const res = await api.listPromptVersions(workspaceId, slug);
      setVersions(res.versions || []);
      if (res.versions && res.versions.length > 0) {
        setContent(res.versions[0].content);
        setSelectedVersion(res.versions[0].version_number);
      }
    } catch (err: any) {
      console.warn("Could not load prompt versions:", err?.message || err);
      setVersions([]);
    } finally {
      setLoading(false);
    }
  }, [workspaceId, slug]);

  useEffect(() => {
    fetchVersions();
  }, [fetchVersions]);

  const handleSaveVersion = async () => {
    if (!workspaceId || !content.trim()) return;
    setSaving(true);
    try {
      await api.createPromptVersion(workspaceId, slug, {
        content,
        commit_message: commitMessage || "Updated prompt template",
        environment: "DEV",
      });
      setCommitMessage("");
      await fetchVersions();
    } catch (err: any) {
      alert("Failed saving prompt version: " + (err.message || err));
    } finally {
      setSaving(false);
    }
  };

  const handlePromote = async (env: "STAGING" | "PROD") => {
    if (!workspaceId || selectedVersion === null) return;
    setPromoting(true);
    try {
      await api.promotePromptVersion(workspaceId, slug, selectedVersion, env);
      await fetchVersions();
    } catch (err: any) {
      alert("Failed promoting prompt: " + (err.message || err));
    } finally {
      setPromoting(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Left Editor Canvas */}
      <div className="lg:col-span-2 space-y-4">
        <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-md space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Code2 className="w-4 h-4 text-sky-400" />
              <span className="text-sm font-bold text-white font-mono">{slug}.jinja2</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono text-slate-400">
                Variables: <code className="text-sky-400">{"{{ context }}"}</code>,{" "}
                <code className="text-sky-400">{"{{ query }}"}</code>
              </span>
            </div>
          </div>

          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={12}
            className="w-full rounded-xl bg-slate-950 border border-slate-800 p-4 font-mono text-xs text-slate-200 focus:outline-none focus:border-sky-500 transition leading-relaxed"
            placeholder="Write sandboxed Jinja2 system prompt..."
          />

          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
            <input
              type="text"
              value={commitMessage}
              onChange={(e) => setCommitMessage(e.target.value)}
              placeholder="Commit summary (e.g. Strict legal citation requirement)..."
              className="w-full sm:w-80 rounded-xl bg-slate-950 border border-slate-800 px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
            />
            <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={handleSaveVersion}
                disabled={saving}
                className="flex items-center gap-1.5"
              >
                {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                <span>Save New Version (DEV)</span>
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Right Version & Promotion History */}
      <div className="space-y-4">
        <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-md space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-mono uppercase tracking-wider text-slate-400">Version History</h4>
            <div className="flex items-center gap-2">
              <Button
                variant="primary"
                size="sm"
                onClick={() => handlePromote("PROD")}
                disabled={promoting || selectedVersion === null}
                className="flex items-center gap-1 text-[11px] px-2.5 py-1"
              >
                <Rocket className="w-3 h-3" />
                <span>Promote to PROD</span>
              </Button>
            </div>
          </div>

          <div className="space-y-2.5">
            {versions.map((ver) => (
              <div
                key={ver.id || ver.version_number}
                onClick={() => {
                  setSelectedVersion(ver.version_number);
                  setContent(ver.content);
                }}
                className={`p-3 rounded-xl border transition cursor-pointer ${
                  selectedVersion === ver.version_number
                    ? "bg-slate-800/80 border-sky-500/50"
                    : "bg-slate-950/60 border-slate-800 hover:border-slate-700"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold text-white">v{ver.version_number}</span>
                  <Badge
                    variant={
                      ver.environment === "PROD" ? "success" : ver.environment === "STAGING" ? "primary" : "outline"
                    }
                  >
                    {ver.environment}
                  </Badge>
                </div>
                <p className="text-[11px] text-slate-400 mt-1 line-clamp-2">
                  {ver.commit_message || "No commit message"}
                </p>
                <div className="flex items-center justify-between text-[10px] text-slate-500 mt-2 font-mono">
                  <span>~{ver.token_count || 35} tokens</span>
                  <span>{ver.is_active ? "Active" : "Archived"}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
