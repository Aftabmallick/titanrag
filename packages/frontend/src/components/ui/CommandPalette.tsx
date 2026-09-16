"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  MessageSquare,
  FileText,
  Sliders,
  FolderSync,
  BarChart3,
  Moon,
  Sun,
  Plus,
  ArrowRight,
  Sparkles,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";

export interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenSettings?: () => void;
}

interface CommandItem {
  id: string;
  category: "Navigation" | "Actions" | "Preferences";
  title: string;
  subtitle?: string;
  icon: React.ReactNode;
  action: () => void;
}

export function CommandPalette({ isOpen, onClose, onOpenSettings }: CommandPaletteProps) {
  const router = useRouter();
  const { workspaces, activeWorkspace, setActiveWorkspace } = useAuth();
  const { resolvedTheme, toggleTheme } = useTheme();

  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  const baseCommands: CommandItem[] = [
    {
      id: "nav-chat",
      category: "Navigation",
      title: "Go to Chat Workstation",
      subtitle: "Grounded research and conversational QA",
      icon: <MessageSquare className="w-4 h-4 text-sky-400" />,
      action: () => {
        router.push("/");
        onClose();
      },
    },
    {
      id: "nav-documents",
      category: "Navigation",
      title: "Go to Knowledge Documents",
      subtitle: "Manage PDF, DOCX, CSV files and ingestion state",
      icon: <FileText className="w-4 h-4 text-emerald-400" />,
      action: () => {
        router.push("/documents");
        onClose();
      },
    },
    {
      id: "nav-connectors",
      category: "Navigation",
      title: "Go to SaaS Connectors",
      subtitle: "Google Drive, SharePoint, Confluence and Notion CDC",
      icon: <FolderSync className="w-4 h-4 text-indigo-400" />,
      action: () => {
        router.push("/connectors");
        onClose();
      },
    },
    {
      id: "nav-analytics",
      category: "Navigation",
      title: "Go to Analytics & FinOps",
      subtitle: "Telemetry, latency distribution and CU quota monitoring",
      icon: <BarChart3 className="w-4 h-4 text-amber-400" />,
      action: () => {
        router.push("/analytics");
        onClose();
      },
    },
    {
      id: "act-new-chat",
      category: "Actions",
      title: "Start New Research Chat",
      subtitle: "Clear active context and launch blank session",
      icon: <Plus className="w-4 h-4 text-sky-400" />,
      action: () => {
        router.push("/");
        onClose();
      },
    },
    {
      id: "act-settings",
      category: "Actions",
      title: "Open RAG Parameter Drawer",
      subtitle: "Tune hybrid alpha, reranker, confidence threshold, and prompt",
      icon: <Sliders className="w-4 h-4 text-sky-400" />,
      action: () => {
        onClose();
        if (onOpenSettings) onOpenSettings();
      },
    },
    {
      id: "pref-theme",
      category: "Preferences",
      title: `Switch to ${resolvedTheme === "dark" ? "Light" : "Dark"} Mode`,
      subtitle: "Toggle between high-contrast dark and light themes",
      icon: resolvedTheme === "dark" ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-indigo-400" />,
      action: () => {
        toggleTheme();
        onClose();
      },
    },
  ];

  // Include workspace switcher items
  const workspaceCommands: CommandItem[] = workspaces.map((ws) => ({
    id: `ws-${ws.id}`,
    category: "Navigation",
    title: `Switch Workspace: ${ws.name}`,
    subtitle: ws.description || `Tenant ID: ${ws.tenant_id}`,
    icon: <Sparkles className="w-4 h-4 text-sky-400" />,
    action: () => {
      setActiveWorkspace(ws);
      onClose();
    },
  }));

  const allCommands = [...baseCommands, ...workspaceCommands];

  const filteredCommands = allCommands.filter((cmd) => {
    const term = query.toLowerCase();
    return (
      cmd.title.toLowerCase().includes(term) ||
      (cmd.subtitle && cmd.subtitle.toLowerCase().includes(term)) ||
      cmd.category.toLowerCase().includes(term)
    );
  });

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % Math.max(1, filteredCommands.length));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + filteredCommands.length) % Math.max(1, filteredCommands.length));
    } else if (e.key === "Enter" && filteredCommands[selectedIndex]) {
      e.preventDefault();
      filteredCommands[selectedIndex].action();
    } else if (e.key === "Escape") {
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Command Palette"
      className="fixed inset-0 z-50 flex items-start justify-center pt-20 sm:pt-28 p-4 bg-slate-950/80 backdrop-blur-md animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl overflow-hidden animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        {/* Search input header */}
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-slate-800 bg-slate-900/60">
          <Search className="w-4 h-4 text-sky-400 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Type a command or search workspaces, documents, actions..."
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            className="w-full bg-transparent text-sm text-slate-100 placeholder-slate-500 focus:outline-none"
          />
          <kbd className="hidden sm:inline-block px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-[10px] font-mono text-slate-400">
            ESC
          </kbd>
        </div>

        {/* Results List */}
        <div className="max-h-80 overflow-y-auto p-2 space-y-1">
          {filteredCommands.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-500">
              No matching commands found for &quot;{query}&quot;
            </div>
          ) : (
            filteredCommands.map((cmd, idx) => {
              const isSelected = idx === selectedIndex;
              return (
                <button
                  key={cmd.id}
                  onClick={() => cmd.action()}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`w-full flex items-center justify-between p-2.5 rounded-xl text-left transition-all ${
                    isSelected
                      ? "bg-sky-500/15 border border-sky-500/30 text-white"
                      : "hover:bg-slate-800/60 text-slate-300"
                  }`}
                >
                  <div className="flex items-center gap-3 overflow-hidden">
                    <div className="p-2 rounded-lg bg-slate-800 text-slate-300 shrink-0">
                      {cmd.icon}
                    </div>
                    <div className="truncate">
                      <div className="text-xs font-semibold text-slate-100 truncate">{cmd.title}</div>
                      {cmd.subtitle && (
                        <div className="text-[11px] text-slate-400 truncate">{cmd.subtitle}</div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0 pl-2">
                    <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                      {cmd.category}
                    </span>
                    {isSelected && <ArrowRight className="w-3.5 h-3.5 text-sky-400" />}
                  </div>
                </button>
              );
            })
          )}
        </div>

        {/* Footer shortcuts helper */}
        <div className="px-4 py-2 bg-slate-950/60 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-500 font-mono">
          <span>Navigate: ↑ ↓</span>
          <span>Select: ↵ Enter</span>
          <span>Close: Esc</span>
        </div>
      </div>
    </div>
  );
}
