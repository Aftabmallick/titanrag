"use client";

import React, { useState, useEffect } from "react";
import { Key, Plus, Trash2, CheckCircle2, Copy, Shield, Loader2 } from "lucide-react";
import { api, ApiKeyRecord } from "@/lib/api";

export function ApiKeysView() {
  const [keys, setKeys] = useState<ApiKeyRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [newKeyRole, setNewKeyRole] = useState("ADMIN");
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const fetchKeys = async () => {
    try {
      setLoading(true);
      const res = await api.listApiKeys();
      setKeys(res);
    } catch (err: any) {
      console.warn("Could not fetch API keys:", err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchKeys();
  }, []);

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKeyName.trim()) return;
    setCreating(true);
    try {
      const res = await api.createApiKey(newKeyName.trim(), newKeyRole, 90);
      setGeneratedKey(res.api_key);
      setNewKeyName("");
      await fetchKeys();
    } catch (err: any) {
      alert("Failed to create API key: " + err.message);
    } finally {
      setCreating(false);
    }
  };

  const handleRevokeKey = async (id: string) => {
    if (!confirm("Are you sure you want to revoke this API key? Applications using it will lose access immediately.")) {
      return;
    }
    try {
      await api.revokeApiKey(id);
      await fetchKeys();
    } catch (err: any) {
      alert("Failed to revoke key: " + err.message);
    }
  };

  const handleCopy = () => {
    if (generatedKey) {
      navigator.clipboard.writeText(generatedKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-xl shadow-2xl space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <Key className="w-5 h-5 text-indigo-400" />
            API Key Credentials
          </h2>
          <p className="text-sm text-slate-400">
            Cryptographically hashed (SHA-256) API keys for headless ingestions and automated SDK pipelines
          </p>
        </div>
      </div>

      {/* New Key Generated Alert */}
      {generatedKey && (
        <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-950/20 text-emerald-200 space-y-2">
          <div className="flex items-center gap-2 text-sm font-semibold text-emerald-400">
            <CheckCircle2 className="w-4 h-4" />
            <span>API Key Created Successfully — Save it now!</span>
          </div>
          <p className="text-xs text-slate-300">
            For security, this secret token will never be displayed again.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-emerald-300 select-all">
              {generatedKey}
            </code>
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-bold transition-colors cursor-pointer"
            >
              <Copy className="w-3.5 h-3.5" />
              <span>{copied ? "Copied!" : "Copy"}</span>
            </button>
          </div>
        </div>
      )}

      {/* Create Key Form */}
      <form onSubmit={handleCreateKey} className="flex flex-wrap items-end gap-3 p-4 rounded-xl border border-slate-800 bg-slate-950/50">
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs font-semibold text-slate-300 mb-1">Key Description</label>
          <input
            type="text"
            required
            placeholder="e.g. CI Pipeline Uploader"
            value={newKeyName}
            onChange={(e) => setNewKeyName(e.target.value)}
            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div className="w-40">
          <label className="block text-xs font-semibold text-slate-300 mb-1">Role Scope</label>
          <select
            value={newKeyRole}
            onChange={(e) => setNewKeyRole(e.target.value)}
            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-indigo-500 cursor-pointer"
          >
            <option value="ADMIN">Admin</option>
            <option value="MEMBER">Member</option>
            <option value="VIEWER">Viewer</option>
          </select>
        </div>

        <button
          type="submit"
          disabled={creating}
          className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-colors disabled:opacity-50 cursor-pointer"
        >
          {creating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
          <span>Generate Key</span>
        </button>
      </form>

      {/* Key Table */}
      <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/50">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-slate-900/80 text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800">
            <tr>
              <th className="py-3 px-4 font-semibold">Name</th>
              <th className="py-3 px-4 font-semibold">Prefix</th>
              <th className="py-3 px-4 font-semibold">Role</th>
              <th className="py-3 px-4 font-semibold">Created</th>
              <th className="py-3 px-4 font-semibold">Expires</th>
              <th className="py-3 px-4 font-semibold text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {loading ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-slate-500">
                  Loading keys...
                </td>
              </tr>
            ) : keys.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-slate-500">
                  No active API keys found. Generate a key above to enable programmatic access.
                </td>
              </tr>
            ) : (
              keys.map((k) => (
                <tr key={k.id} className="hover:bg-slate-900/40 transition-colors">
                  <td className="py-3 px-4 font-semibold text-white">{k.name}</td>
                  <td className="py-3 px-4 font-mono text-slate-400">{k.key_prefix}...</td>
                  <td className="py-3 px-4">
                    <span className="px-2 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 font-mono text-[10px]">
                      {k.role}
                    </span>
                  </td>
                  <td className="py-3 px-4 font-mono text-slate-400">
                    {new Date(k.created_at).toLocaleDateString()}
                  </td>
                  <td className="py-3 px-4 font-mono text-slate-400">
                    {k.expires_at ? new Date(k.expires_at).toLocaleDateString() : "Never"}
                  </td>
                  <td className="py-3 px-4 text-right">
                    <button
                      onClick={() => handleRevokeKey(k.id)}
                      className="p-1.5 rounded-lg border border-slate-800 hover:border-rose-500/40 hover:bg-rose-500/10 text-slate-400 hover:text-rose-400 transition-colors"
                      title="Revoke API key"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
