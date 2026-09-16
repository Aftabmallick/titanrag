"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Layers,
  MessageSquare,
  FileText,
  Sliders,
  BarChart3,
  ShieldAlert,
  Plus,
  ChevronLeft,
  ChevronRight,
  FolderSync,
  Trash2,
  Edit2,
  Check,
  X,
  Share2,
  FolderTree,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { api, ChatSessionRecord } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { useToast } from "@/components/ui/Toast";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: any[]) {
  return twMerge(clsx(inputs));
}

export interface SidebarProps {
  activeView: "chat" | "documents" | "connectors" | "analytics" | "admin";
  onSelectView: (view: "chat" | "documents" | "connectors" | "analytics" | "admin") => void;
  onOpenSettings: () => void;
  activeSessionId?: string | null;
  onSelectSession?: (sessionId: string) => void;
  onNewChat?: () => void;
}

export function Sidebar({
  activeView,
  onSelectView,
  onOpenSettings,
  activeSessionId,
  onSelectSession,
  onNewChat,
}: SidebarProps) {
  const { user, workspaces, activeWorkspace, setActiveWorkspace, refreshWorkspaces } = useAuth();
  const { success, error } = useToast();

  const { t } = useI18n();

  const [collapsed, setCollapsed] = useState(false);
  const [sessions, setSessions] = useState<ChatSessionRecord[]>([]);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [createWsOpen, setCreateWsOpen] = useState(false);
  const [newWsName, setNewWsName] = useState("");
  const [creatingWs, setCreatingWs] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("titan_sidebar_collapsed");
    if (stored === "true") setCollapsed(true);
  }, []);

  const toggleCollapse = () => {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem("titan_sidebar_collapsed", next ? "true" : "false");
  };

  const fetchSessions = useCallback(async () => {
    if (!activeWorkspace) return;
    try {
      const list = await api.listChatSessions(activeWorkspace.id);
      setSessions(list);
    } catch {
      // ignore
    }
  }, [activeWorkspace]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const handleCreateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWsName.trim()) return;
    setCreatingWs(true);
    try {
      const created = await api.createWorkspace(newWsName.trim());
      await refreshWorkspaces();
      setActiveWorkspace(created);
      setNewWsName("");
      setCreateWsOpen(false);
      success("Workspace Created", `"${created.name}" is now active.`);
    } catch (err: any) {
      error("Creation failed", err.message);
    } finally {
      setCreatingWs(false);
    }
  };

  const handleRenameSession = async (sessionId: string) => {
    if (!activeWorkspace || !editingTitle.trim()) {
      setEditingSessionId(null);
      return;
    }
    try {
      await api.updateChatSession(activeWorkspace.id, sessionId, editingTitle.trim());
      setSessions((prev) =>
        prev.map((s) => (s.id === sessionId ? { ...s, title: editingTitle.trim() } : s))
      );
      setEditingSessionId(null);
    } catch (err: any) {
      error("Could not rename session", err.message);
    }
  };

  const handleDeleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    if (!activeWorkspace) return;
    try {
      await api.deleteChatSession(activeWorkspace.id, sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (activeSessionId === sessionId && onNewChat) {
        onNewChat();
      }
    } catch (err: any) {
      error("Could not delete session", err.message);
    }
  };

  return (
    <>
      <aside
        className={cn(
          "h-screen sticky top-0 border-r border-slate-800/80 bg-slate-950 flex flex-col justify-between transition-all duration-300 z-40",
          collapsed ? "w-16" : "w-64 sm:w-72"
        )}
      >
        {/* Top Segment: Brand & Workspace Switcher */}
        <div className="flex flex-col h-full overflow-hidden">
          {/* Header */}
          <div className="h-14 border-b border-slate-800/80 px-4 flex items-center justify-between">
            <div className="flex items-center gap-2.5 overflow-hidden">
              <div className="p-1.5 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 text-white shadow-md shadow-sky-500/25 shrink-0">
                <Layers className="w-4 h-4" />
              </div>
              {!collapsed && (
                <span className="font-extrabold text-sm tracking-tight text-white truncate">
                  TitanRAG
                </span>
              )}
            </div>
            <button
              onClick={toggleCollapse}
              className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-900 transition-colors"
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
            </button>
          </div>

          {/* Workspace Switcher */}
          {!collapsed && activeWorkspace && (
            <div className="p-3 border-b border-slate-800/80 space-y-2">
              <div className="flex items-center justify-between text-[11px] text-slate-400 font-medium px-1">
                <span>Active Domain</span>
                <span className="px-1.5 py-0.2 rounded-full bg-sky-500/10 border border-sky-500/20 text-sky-400 font-mono text-[9px] font-bold">
                  {user?.role || "MEMBER"}
                </span>
              </div>
              <div className="flex items-center justify-between gap-2 p-2 rounded-xl bg-slate-900/90 border border-slate-800">
                <div className="flex items-center gap-2 overflow-hidden flex-1">
                  <FolderSync className="w-3.5 h-3.5 text-sky-400 shrink-0" />
                  <select
                    value={activeWorkspace.id}
                    onChange={(e) => {
                      const found = workspaces.find((w) => w.id === e.target.value);
                      if (found) setActiveWorkspace(found);
                    }}
                    className="w-full bg-transparent text-xs font-semibold text-slate-200 focus:outline-none cursor-pointer truncate"
                  >
                    {workspaces.map((ws) => (
                      <option key={ws.id} value={ws.id} className="bg-slate-900 text-slate-200">
                        {ws.name}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={() => setCreateWsOpen(true)}
                  className="p-1 rounded-md text-slate-400 hover:text-sky-400 hover:bg-slate-800 transition-colors shrink-0"
                  title="Create Workspace"
                >
                  <Plus className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          )}

          {/* Primary Navigation Items */}
          <div className="p-2 space-y-1">
            <button
              onClick={() => {
                onSelectView("chat");
                if (onNewChat) onNewChat();
              }}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-semibold transition-all",
                "bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white shadow-md shadow-sky-500/20"
              )}
            >
              <Plus className="w-4 h-4 shrink-0" />
              {!collapsed && <span>{t("nav.newChat", "New Chat")}</span>}
            </button>

            <button
              onClick={() => onSelectView("chat")}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-semibold transition-colors",
                activeView === "chat"
                  ? "bg-slate-800 text-sky-400 font-bold border border-slate-700/60"
                  : "text-slate-300 hover:bg-slate-900 hover:text-white"
              )}
            >
              <MessageSquare className="w-4 h-4 shrink-0" />
              {!collapsed && <span>{t("nav.chat", "Chat Assistant")}</span>}
            </button>

            <button
              onClick={() => onSelectView("documents")}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-semibold transition-colors",
                activeView === "documents"
                  ? "bg-slate-800 text-sky-400 font-bold border border-slate-700/60"
                  : "text-slate-300 hover:bg-slate-900 hover:text-white"
              )}
            >
              <FileText className="w-4 h-4 shrink-0" />
              {!collapsed && <span>{t("nav.documents", "Knowledge Documents")}</span>}
            </button>

            <button
              onClick={() => onSelectView("connectors")}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-semibold transition-colors",
                activeView === "connectors"
                  ? "bg-slate-800 text-sky-400 font-bold border border-slate-700/60"
                  : "text-slate-300 hover:bg-slate-900 hover:text-white"
              )}
            >
              <FolderTree className="w-4 h-4 shrink-0" />
              {!collapsed && <span>{t("nav.connectors", "SaaS Connectors")}</span>}
            </button>

            <button
              onClick={onOpenSettings}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-semibold transition-colors",
                "text-slate-300 hover:bg-slate-900 hover:text-white"
              )}
            >
              <Sliders className="w-4 h-4 shrink-0 text-sky-400" />
              {!collapsed && <span>{t("nav.settings", "RAG Tuning Panel")}</span>}
            </button>

            <button
              onClick={() => onSelectView("analytics")}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-semibold transition-colors",
                activeView === "analytics"
                  ? "bg-slate-800 text-sky-400 font-bold border border-slate-700/60"
                  : "text-slate-300 hover:bg-slate-900 hover:text-white"
              )}
            >
              <BarChart3 className="w-4 h-4 shrink-0" />
              {!collapsed && <span>{t("nav.analytics", "Analytics & FinOps")}</span>}
            </button>

            <button
              onClick={() => onSelectView("admin")}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-semibold transition-colors",
                activeView === "admin"
                  ? "bg-slate-800 text-sky-400 font-bold border border-slate-700/60"
                  : "text-slate-300 hover:bg-slate-900 hover:text-white"
              )}
            >
              <ShieldAlert className="w-4 h-4 shrink-0" />
              {!collapsed && <span>{t("nav.admin", "Admin & DLQ")}</span>}
            </button>
          </div>

          {/* Chat Sessions History */}
          {!collapsed && (
            <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1 border-t border-slate-800/80 mt-2">
              <div className="px-2 py-1 text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                Recent Sessions
              </div>
              {sessions.length === 0 ? (
                <div className="px-3 py-4 text-center text-xs text-slate-500 italic">
                  No previous sessions
                </div>
              ) : (
                sessions.map((sess) => {
                  const isActive = sess.id === activeSessionId;
                  const isEditing = sess.id === editingSessionId;

                  return (
                    <div
                      key={sess.id}
                      onClick={() => {
                        onSelectView("chat");
                        if (onSelectSession) onSelectSession(sess.id);
                      }}
                      className={cn(
                        "group relative flex items-center justify-between px-2.5 py-2 rounded-xl text-xs cursor-pointer transition-colors",
                        isActive
                          ? "bg-slate-800/90 text-white font-medium border border-slate-700/60"
                          : "text-slate-400 hover:bg-slate-900/60 hover:text-slate-200"
                      )}
                    >
                      {isEditing ? (
                        <div
                          className="flex items-center gap-1.5 w-full"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <input
                            type="text"
                            value={editingTitle}
                            onChange={(e) => setEditingTitle(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") handleRenameSession(sess.id);
                              if (e.key === "Escape") setEditingSessionId(null);
                            }}
                            autoFocus
                            className="flex-1 bg-slate-950 border border-sky-500 rounded px-1.5 py-0.5 text-xs text-white focus:outline-none"
                          />
                          <button
                            onClick={() => handleRenameSession(sess.id)}
                            className="p-1 text-emerald-400 hover:text-emerald-300"
                          >
                            <Check className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => setEditingSessionId(null)}
                            className="p-1 text-slate-400 hover:text-slate-200"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ) : (
                        <>
                          <div className="flex items-center gap-2 truncate flex-1 pr-2">
                            <MessageSquare className="w-3.5 h-3.5 shrink-0 text-slate-500 group-hover:text-slate-400" />
                            <span className="truncate">{sess.title || "New Chat"}</span>
                          </div>
                          <div className="opacity-0 group-hover:opacity-100 flex items-center gap-1 transition-opacity">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setEditingSessionId(sess.id);
                                setEditingTitle(sess.title || "");
                              }}
                              className="p-1 text-slate-400 hover:text-slate-200"
                              title="Rename"
                            >
                              <Edit2 className="w-3 h-3" />
                            </button>
                            <button
                              onClick={(e) => handleDeleteSession(e, sess.id)}
                              className="p-1 text-slate-400 hover:text-rose-400"
                              title="Delete"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>
      </aside>

      {/* Create Workspace Modal */}
      <Modal
        isOpen={createWsOpen}
        onClose={() => setCreateWsOpen(false)}
        title="Create New Knowledge Workspace"
        description="Configure an isolated workspace with tenant boundary guarantees."
      >
        <form onSubmit={handleCreateWorkspace} className="space-y-4">
          <Input
            label="Workspace Name"
            placeholder="Finance & Tax Operations"
            value={newWsName}
            onChange={(e) => setNewWsName(e.target.value)}
            required
            autoFocus
          />
          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setCreateWsOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" variant="primary" size="sm" loading={creatingWs}>
              Create Workspace
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
