"use client";

import React, { useState } from "react";
import { FolderSync, Plus, Check, ChevronDown } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";

export function WorkspaceSwitcher() {
  const { user, workspaces, activeWorkspace, setActiveWorkspace, refreshWorkspaces } = useAuth();
  const [showNewWsModal, setShowNewWsModal] = useState(false);
  const [newWsName, setNewWsName] = useState("");
  const [creatingWs, setCreatingWs] = useState(false);
  const { success, error } = useToast();

  if (!user) return null;

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
      success("Workspace Created", `"${created.name}" is now active.`);
    } catch (err: any) {
      error("Failed to create workspace", err.message || "Please retry");
    } finally {
      setCreatingWs(false);
    }
  };

  return (
    <>
      <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900/80 text-xs text-slate-200 hover:border-slate-700 transition-colors">
        <FolderSync className="w-3.5 h-3.5 text-sky-400 shrink-0" />
        <select
          className="bg-transparent border-none text-slate-200 text-xs focus:ring-0 cursor-pointer pr-4 outline-none font-medium"
          value={activeWorkspace?.id || ""}
          onChange={(e) => {
            const ws = workspaces.find((w) => w.id === e.target.value);
            if (ws) setActiveWorkspace(ws);
          }}
        >
          {workspaces.map((w) => (
            <option key={w.id} value={w.id} className="bg-slate-900 text-white">
              {w.name}
            </option>
          ))}
        </select>
        <button
          title="Create New Workspace"
          onClick={() => setShowNewWsModal(true)}
          className="p-1 hover:bg-slate-800 rounded transition-colors text-slate-400 hover:text-white"
        >
          <Plus className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* New Workspace Modal */}
      {showNewWsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-sm p-6 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
            <h3 className="text-base font-bold text-white mb-1">Create Workspace</h3>
            <p className="text-xs text-slate-400 mb-4">
              Workspaces isolate documents, vectors, and ACL security groups.
            </p>
            <form onSubmit={handleCreateWorkspace}>
              <input
                type="text"
                placeholder="e.g. Legal & Contracts"
                value={newWsName}
                onChange={(e) => setNewWsName(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 mb-4"
                autoFocus
              />
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  onClick={() => setShowNewWsModal(false)}
                  className="px-3 py-1.5 rounded-lg border border-slate-700 text-slate-300 text-xs hover:bg-slate-800 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingWs || !newWsName.trim()}
                  className="px-3 py-1.5 rounded-lg bg-sky-500 text-white text-xs font-semibold hover:bg-sky-400 disabled:opacity-50 transition-colors"
                >
                  {creatingWs ? "Creating..." : "Create"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
