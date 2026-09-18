"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Webhook,
  Plus,
  Activity,
  Check,
  AlertTriangle,
  XCircle,
  Copy,
  Trash2,
  RefreshCw,
  ExternalLink,
  Clock,
  Shield,
  Zap,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/components/ui/Toast";

interface PluginRecord {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  version: string;
  endpoint_url: string;
  webhook_secret_masked: string;
  hooks: string[];
  timeout_ms: number;
  retry_count: number;
  is_active: boolean;
  health_status: "HEALTHY" | "DEGRADED" | "OFFLINE";
  last_ping_at: string | null;
  failure_count: number;
  circuit_tripped: boolean;
  created_at: string;
}

interface LogRecord {
  id: string;
  hook_type: string;
  status_code: number | null;
  latency_ms: number;
  error_message: string | null;
  timestamp: string;
}

export default function PluginsAdminPage() {
  const { activeWorkspace } = useAuth();
  const { success, error } = useToast();

  const [plugins, setPlugins] = useState<PluginRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [registerModalOpen, setRegisterModalOpen] = useState(false);
  const [createdSecret, setCreatedSecret] = useState<string | null>(null);
  const [copiedSecret, setCopiedSecret] = useState(false);

  // Form inputs for new plugin
  const [formName, setFormName] = useState("");
  const [formUrl, setFormUrl] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formTimeout, setFormTimeout] = useState(2000);
  const [formHooks, setFormHooks] = useState<string[]>(["ON_PARSE", "ON_POST_GENERATE"]);
  const [submitting, setSubmitting] = useState(false);

  // Ping probe state
  const [pingingId, setPingingId] = useState<string | null>(null);
  const [pingResult, setPingResult] = useState<{ id: string; success: boolean; latency: number; error?: string } | null>(null);

  // Logs drawer state
  const [selectedPluginForLogs, setSelectedPluginForLogs] = useState<PluginRecord | null>(null);
  const [logs, setLogs] = useState<LogRecord[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(false);

  const fetchPlugins = useCallback(async () => {
    if (!activeWorkspace) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/v1/workspaces/${activeWorkspace.id}/plugins`);
      if (res.ok) {
        const data = await res.json();
        setPlugins(data);
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [activeWorkspace]);

  useEffect(() => {
    fetchPlugins();
  }, [fetchPlugins]);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeWorkspace || !formName.trim() || !formUrl.trim()) return;

    setSubmitting(true);
    try {
      const res = await fetch(`/api/v1/workspaces/${activeWorkspace.id}/plugins`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: formName.trim(),
          endpoint_url: formUrl.trim(),
          description: formDescription.trim() || null,
          timeout_ms: formTimeout,
          hooks: formHooks,
          is_active: true,
        }),
      });

      if (!res.ok) {
        const errJson = await res.json();
        throw new Error(errJson.detail || "Failed to register plugin");
      }

      const created = await res.json();
      setCreatedSecret(created.webhook_secret);
      success("Plugin registered successfully!");
      fetchPlugins();
    } catch (err: any) {
      error(err.message || "Failed to register plugin");
    } finally {
      setSubmitting(false);
    }
  };

  const handlePing = async (pluginId: string) => {
    if (!activeWorkspace) return;
    setPingingId(pluginId);
    setPingResult(null);

    try {
      const res = await fetch(`/api/v1/workspaces/${activeWorkspace.id}/plugins/${pluginId}/ping`, {
        method: "POST",
      });
      const data = await res.json();
      setPingResult({
        id: pluginId,
        success: data.success,
        latency: data.latency_ms,
        error: data.error,
      });

      if (data.success) {
        success(`Ping OK (${data.latency_ms} ms)`);
      } else {
        error(`Ping failed: ${data.error || "Remote endpoint unreachable"}`);
      }
      fetchPlugins();
    } catch (err: any) {
      error(err.message || "Ping error");
    } finally {
      setPingingId(null);
    }
  };

  const handleDelete = async (pluginId: string) => {
    if (!activeWorkspace || !confirm("Are you sure you want to deregister this plugin?")) return;
    try {
      await fetch(`/api/v1/workspaces/${activeWorkspace.id}/plugins/${pluginId}`, {
        method: "DELETE",
      });
      success("Plugin deregistered");
      fetchPlugins();
    } catch (err: any) {
      error(err.message || "Failed to delete plugin");
    }
  };

  const handleToggleActive = async (plugin: PluginRecord) => {
    if (!activeWorkspace) return;
    try {
      await fetch(`/api/v1/workspaces/${activeWorkspace.id}/plugins/${plugin.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: !plugin.is_active }),
      });
      fetchPlugins();
    } catch {
      // ignore
    }
  };

  const viewLogs = async (plugin: PluginRecord) => {
    setSelectedPluginForLogs(plugin);
    setLoadingLogs(true);
    try {
      const res = await fetch(`/api/v1/workspaces/${activeWorkspace?.id}/plugins/${plugin.id}/logs`);
      if (res.ok) {
        setLogs(await res.json());
      }
    } catch {
      // ignore
    } finally {
      setLoadingLogs(false);
    }
  };

  const toggleHook = (h: string) => {
    if (formHooks.includes(h)) {
      if (formHooks.length > 1) {
        setFormHooks(formHooks.filter((item) => item !== h));
      }
    } else {
      setFormHooks([...formHooks, h]);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono px-2 py-0.5 rounded-full border border-sky-500/30 bg-sky-500/10 text-sky-400">
              Extension Framework
            </span>
            <span className="text-xs text-slate-500">Phase 7 Micro-Hooks</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Webhook className="w-6 h-6 text-sky-400" />
            Webhook Micro-Hook Plugins
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Execute out-of-process custom parsers, chunkers, rerankers, and egress compliance filters with HMAC-SHA256 signing and circuit breakers.
          </p>
        </div>

        <button
          onClick={() => {
            setCreatedSecret(null);
            setRegisterModalOpen(true);
          }}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white font-semibold text-xs shadow-md shadow-sky-500/20 transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>Register Plugin</span>
        </button>
      </div>

      {/* Plugins Table / Empty State */}
      {loading ? (
        <div className="flex items-center justify-center h-48 text-slate-500 gap-2">
          <RefreshCw className="w-5 h-5 animate-spin text-sky-400" />
          <span>Loading registered plugins...</span>
        </div>
      ) : plugins.length === 0 ? (
        <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-12 text-center space-y-4">
          <div className="w-12 h-12 rounded-2xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center mx-auto text-sky-400">
            <Webhook className="w-6 h-6" />
          </div>
          <h3 className="text-base font-semibold text-white">No Plugins Registered</h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            Connect external webhooks to intercept document parsing, vector reranking, or egress moderation without running arbitrary code in container workers.
          </p>
          <button
            onClick={() => {
              setCreatedSecret(null);
              setRegisterModalOpen(true);
            }}
            className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-sky-500 hover:bg-sky-400 text-white text-xs font-semibold"
          >
            <Plus className="w-4 h-4" />
            <span>Register First Plugin</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {plugins.map((plugin) => (
            <div
              key={plugin.id}
              className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 transition-all hover:border-slate-700"
            >
              <div className="space-y-2 max-w-xl">
                <div className="flex items-center gap-3">
                  <span className="font-bold text-base text-white">{plugin.name}</span>
                  <span className="text-[11px] font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded">
                    v{plugin.version}
                  </span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-semibold border ${
                      plugin.health_status === "HEALTHY"
                        ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                        : "bg-rose-500/15 text-rose-400 border-rose-500/30"
                    }`}
                  >
                    {plugin.health_status}
                  </span>
                  {plugin.circuit_tripped && (
                    <span className="text-xs px-2 py-0.5 rounded-full font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" /> Circuit Tripped
                    </span>
                  )}
                </div>

                <div className="text-xs font-mono text-slate-400 flex items-center gap-2">
                  <ExternalLink className="w-3.5 h-3.5 text-sky-400 shrink-0" />
                  <span className="truncate">{plugin.endpoint_url}</span>
                </div>

                <div className="flex items-center gap-2 flex-wrap pt-1">
                  <span className="text-xs text-slate-500">Hooks:</span>
                  {plugin.hooks.map((h) => (
                    <span
                      key={h}
                      className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-500/30"
                    >
                      {h}
                    </span>
                  ))}
                  <span className="text-xs text-slate-500 ml-2">Timeout: {plugin.timeout_ms}ms</span>
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handlePing(plugin.id)}
                  disabled={pingingId === plugin.id}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-700 bg-slate-800 hover:bg-slate-750 text-xs font-semibold text-slate-200 transition-colors disabled:opacity-50"
                  title="Send authenticated HMAC ping probe"
                >
                  <Activity className={`w-3.5 h-3.5 ${pingingId === plugin.id ? "animate-spin text-sky-400" : "text-emerald-400"}`} />
                  <span>{pingingId === plugin.id ? "Pinging..." : "Ping Probe"}</span>
                </button>

                <button
                  onClick={() => viewLogs(plugin)}
                  className="px-3 py-1.5 rounded-xl border border-slate-700 bg-slate-800 hover:bg-slate-750 text-xs font-semibold text-slate-200 transition-colors"
                >
                  Logs
                </button>

                <button
                  onClick={() => handleToggleActive(plugin)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-colors ${
                    plugin.is_active
                      ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/25"
                      : "bg-slate-800 text-slate-400 border border-slate-700 hover:text-white"
                  }`}
                >
                  {plugin.is_active ? "Enabled" : "Disabled"}
                </button>

                <button
                  onClick={() => handleDelete(plugin.id)}
                  className="p-2 rounded-xl text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition-colors"
                  title="Deregister Plugin"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Registration Modal */}
      {registerModalOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 space-y-5 shadow-2xl">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Webhook className="w-5 h-5 text-sky-400" />
              Register Webhook Micro-Hook
            </h2>

            {createdSecret ? (
              <div className="space-y-4">
                <div className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl space-y-2">
                  <div className="text-xs font-semibold text-emerald-400 flex items-center gap-1.5">
                    <Check className="w-4 h-4" />
                    Plugin Registered! Copy your HMAC Secret:
                  </div>
                  <p className="text-[11px] text-slate-300">
                    This secret is displayed ONLY ONCE. Configure your webhook microservice to verify incoming requests using HMAC-SHA256 with this secret.
                  </p>
                  <div className="flex items-center justify-between bg-slate-950 p-2.5 rounded-lg border border-slate-800 font-mono text-xs text-amber-300">
                    <span className="truncate">{createdSecret}</span>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(createdSecret);
                        setCopiedSecret(true);
                        setTimeout(() => setCopiedSecret(false), 2000);
                      }}
                      className="text-slate-400 hover:text-white ml-2 shrink-0"
                    >
                      {copiedSecret ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <div className="flex justify-end">
                  <button
                    onClick={() => {
                      setRegisterModalOpen(false);
                      setCreatedSecret(null);
                    }}
                    className="px-4 py-2 rounded-xl bg-sky-500 hover:bg-sky-400 text-white font-semibold text-xs"
                  >
                    Done
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleRegister} className="space-y-4">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-300">Plugin Name</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Legal Contract Parser"
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 outline-none focus:border-sky-500"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-300">Webhook HTTPS Endpoint URL</label>
                  <input
                    type="url"
                    required
                    placeholder="https://service.internal/webhook"
                    value={formUrl}
                    onChange={(e) => setFormUrl(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 font-mono outline-none focus:border-sky-500"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-300">Description (Optional)</label>
                  <input
                    type="text"
                    placeholder="Custom parsing & metadata enrichment"
                    value={formDescription}
                    onChange={(e) => setFormDescription(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 outline-none focus:border-sky-500"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-semibold text-slate-300">Pipeline Hooks Intercepted</label>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {["ON_PARSE", "ON_CHUNK", "ON_EMBED", "ON_RERANK", "ON_POST_GENERATE"].map((h) => (
                      <label
                        key={h}
                        className={`flex items-center gap-2 p-2.5 rounded-xl border cursor-pointer select-none transition-colors ${
                          formHooks.includes(h)
                            ? "bg-sky-500/15 border-sky-500/40 text-sky-300"
                            : "bg-slate-950 border-slate-800 text-slate-400"
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={formHooks.includes(h)}
                          onChange={() => toggleHook(h)}
                          className="hidden"
                        />
                        <span className="font-mono text-[11px] font-bold">{h}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <div className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="font-semibold text-slate-300">Timeout Budget</span>
                    <span className="font-mono text-sky-400">{formTimeout} ms</span>
                  </div>
                  <input
                    type="range"
                    min={200}
                    max={5000}
                    step={100}
                    value={formTimeout}
                    onChange={(e) => setFormTimeout(Number(e.target.value))}
                    className="w-full accent-sky-500"
                  />
                </div>

                <div className="flex items-center justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setRegisterModalOpen(false)}
                    className="px-4 py-2 rounded-xl text-xs text-slate-400 hover:text-white"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="px-4 py-2 rounded-xl bg-sky-500 hover:bg-sky-400 text-white font-semibold text-xs disabled:opacity-50"
                  >
                    {submitting ? "Registering..." : "Register Plugin"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Execution Logs Drawer */}
      {selectedPluginForLogs && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex justify-end">
          <div className="bg-slate-900 border-l border-slate-800 w-full max-w-md h-full p-6 flex flex-col space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="font-bold text-white text-base">Execution Logs</h3>
                <p className="text-xs text-slate-400">{selectedPluginForLogs.name}</p>
              </div>
              <button
                onClick={() => setSelectedPluginForLogs(null)}
                className="text-slate-400 hover:text-white p-1 rounded"
              >
                ✕
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 pr-1">
              {loadingLogs ? (
                <div className="text-xs text-slate-500 flex items-center justify-center h-32 gap-2">
                  <RefreshCw className="w-4 h-4 animate-spin text-sky-400" />
                  <span>Loading logs...</span>
                </div>
              ) : logs.length === 0 ? (
                <div className="text-xs text-slate-500 text-center py-12">
                  No executions recorded yet.
                </div>
              ) : (
                logs.map((log) => (
                  <div key={log.id} className="p-3 bg-slate-950 border border-slate-800 rounded-xl space-y-1.5 text-xs font-mono">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-sky-400">{log.hook_type}</span>
                      <span className={`font-semibold ${log.status_code === 200 ? "text-emerald-400" : "text-rose-400"}`}>
                        HTTP {log.status_code || "ERR"}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-400 flex items-center justify-between">
                      <span>Latency: {log.latency_ms} ms</span>
                      <span>{new Date(log.timestamp).toLocaleTimeString()}</span>
                    </div>
                    {log.error_message && (
                      <div className="text-[11px] text-rose-400 pt-1 border-t border-slate-800">
                        {log.error_message}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
