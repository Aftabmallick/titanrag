"use client";

import React, { useState, useEffect } from "react";
import {
  Layers,
  FolderSync,
  Plus,
  LogIn,
  LogOut,
  User as UserIcon,
  Activity,
  CheckCircle2,
  AlertCircle,
  Sparkles,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";

export function Navbar() {
  const { user, workspaces, activeWorkspace, setActiveWorkspace, demoLogin, logout, refreshWorkspaces } = useAuth();
  const [backendStatus, setBackendStatus] = useState<"online" | "offline" | "checking">("checking");
  const [showNewWsModal, setShowNewWsModal] = useState(false);
  const [newWsName, setNewWsName] = useState("");
  const [creatingWs, setCreatingWs] = useState(false);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch("/health/live");
        if (res.ok) {
          setBackendStatus("online");
        } else {
          setBackendStatus("offline");
        }
      } catch {
        setBackendStatus("offline");
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleCreateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWsName.trim()) return;
    setCreatingWs(true);
    try {
      const created = await api.createWorkspace(newWsName.trim());
      await refreshWorkspaces();
      setActiveWorkspace(created);
      setNewWsName("");
      setShowNewWsModal(false);
    } catch (err: any) {
      alert("Failed to create workspace: " + err.message);
    } finally {
      setCreatingWs(false);
    }
  };

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          {/* Logo & Platform Tag */}
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 text-white shadow-lg shadow-sky-500/25">
              <Layers className="w-5 h-5" />
            </div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-base tracking-tight text-white">TitanRAG</span>
              <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full border border-sky-500/30 bg-sky-500/10 text-sky-400">
                Phase 3 Enterprise
              </span>
            </div>
          </div>

          {/* Right Controls: Workspace Selector + Health + Auth */}
          <div className="flex items-center gap-3">
            {/* Backend Health Pill */}
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900/60 text-xs">
              <div
                className={`w-2 h-2 rounded-full ${
                  backendStatus === "online"
                    ? "bg-emerald-400 animate-pulse"
                    : backendStatus === "offline"
                    ? "bg-rose-500"
                    : "bg-amber-400"
                }`}
              />
              <span className="text-slate-400">
                API: <strong className="text-slate-200 capitalize">{backendStatus}</strong>
              </span>
            </div>

            {/* Active Workspace Selector */}
            {user ? (
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900/80 text-xs text-slate-200">
                <FolderSync className="w-3.5 h-3.5 text-sky-400 shrink-0" />
                <select
                  value={activeWorkspace?.id || ""}
                  onChange={(e) => {
                    const ws = workspaces.find((w) => w.id === e.target.value);
                    if (ws) setActiveWorkspace(ws);
                  }}
                  className="bg-transparent border-none focus:outline-none text-slate-100 font-semibold cursor-pointer max-w-[140px] truncate"
                >
                  {workspaces.map((w) => (
                    <option key={w.id} value={w.id} className="bg-slate-900 text-slate-100">
                      {w.name}
                    </option>
                  ))}
                </select>

                <button
                  onClick={() => setShowNewWsModal(true)}
                  title="Create Workspace"
                  className="ml-1 p-0.5 rounded hover:bg-slate-800 text-slate-400 hover:text-sky-400 transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : null}

            {/* User Profile / Quick Login */}
            {user ? (
              <div className="flex items-center gap-2">
                <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900/60 text-xs">
                  <UserIcon className="w-3.5 h-3.5 text-indigo-400" />
                  <span className="text-slate-300 truncate max-w-[120px]">{user.email}</span>
                  <span className="px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-mono text-[10px]">
                    {user.role}
                  </span>
                </div>
                <button
                  onClick={logout}
                  title="Log out"
                  className="p-2 rounded-lg border border-slate-800 bg-slate-900/60 hover:bg-rose-500/20 hover:border-rose-500/40 text-slate-400 hover:text-rose-400 transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <button
                onClick={() => demoLogin()}
                className="flex items-center gap-2 px-4 py-1.5 rounded-lg bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white text-xs font-semibold shadow-md shadow-sky-500/20 transition-all cursor-pointer"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>One-Click Admin Login</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Create Workspace Modal */}
      {showNewWsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl space-y-4">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <FolderSync className="w-5 h-5 text-sky-400" />
              Create New Workspace
            </h3>
            <p className="text-xs text-slate-400">
              Workspaces provide isolated document repositories, vectors, and access controls for your tenant.
            </p>
            <form onSubmit={handleCreateWorkspace} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Workspace Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Legal & Contracts"
                  value={newWsName}
                  onChange={(e) => setNewWsName(e.target.value)}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500"
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowNewWsModal(false)}
                  className="px-4 py-2 rounded-lg border border-slate-700 text-slate-300 text-xs font-medium hover:bg-slate-800 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingWs}
                  className="px-4 py-2 rounded-lg bg-sky-500 hover:bg-sky-400 text-white text-xs font-semibold transition-colors disabled:opacity-50"
                >
                  {creatingWs ? "Creating..." : "Create Workspace"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
