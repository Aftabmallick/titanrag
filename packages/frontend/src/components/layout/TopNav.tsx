"use client";

import React, { useState, useEffect } from "react";
import { UserMenu } from "./UserMenu";
import { LocaleSwitcher } from "./LocaleSwitcher";
import { Breadcrumbs } from "./Breadcrumbs";
import { Command, HelpCircle, Activity, ShieldCheck, Zap, Search } from "lucide-react";
import { ShortcutsModal } from "@/components/ui/ShortcutsModal";
import { CommandPalette } from "@/components/ui/CommandPalette";

export interface TopNavProps {
  title?: string;
  subtitle?: string;
  onOpenSettings?: () => void;
}

export function TopNav({ title = "TitanRAG Workstation", subtitle, onOpenSettings }: TopNavProps) {
  const [healthStatus, setHealthStatus] = useState<"ok" | "degraded" | "down">("ok");
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);

  useEffect(() => {
    const checkLive = async () => {
      try {
        const res = await fetch("/api/v1/health/live");
        if (res.ok) setHealthStatus("ok");
        else setHealthStatus("degraded");
      } catch {
        setHealthStatus("down");
      }
    };
    checkLive();
    const interval = setInterval(checkLive, 15000);
    return () => clearInterval(interval);
  }, []);

  // Listen for Cmd+K globally
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommandPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <>
      <header className="sticky top-0 z-30 h-14 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-xl px-4 sm:px-6 flex items-center justify-between">
        {/* Left: Breadcrumbs & Section */}
        <div className="flex items-center gap-3 overflow-hidden">
          <Breadcrumbs currentTitle={title !== "TitanRAG Workstation" ? title : undefined} />
        </div>

        {/* Right: Search trigger + Health pill + CU FinOps + Shortcuts + User Menu */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Cmd+K Quick Search Button */}
          <button
            onClick={() => setCommandPaletteOpen(true)}
            className="flex items-center gap-2 px-2.5 py-1 rounded-xl border border-slate-800 bg-slate-900/70 hover:bg-slate-800 hover:border-slate-700 text-xs text-slate-400 hover:text-slate-200 transition-all cursor-pointer shadow-sm"
            title="Command Palette (Cmd+K)"
          >
            <Search className="w-3.5 h-3.5 text-sky-400" />
            <span className="hidden md:inline">Quick Search...</span>
            <kbd className="hidden md:inline-flex items-center gap-0.5 px-1.5 py-0.2 rounded bg-slate-800 border border-slate-700 text-[10px] font-mono text-slate-400">
              <Command className="w-2.5 h-2.5" /> K
            </kbd>
          </button>

          {/* Health Pill */}
          <div className="hidden lg:flex items-center gap-2 px-2.5 py-1 rounded-lg border border-slate-800 bg-slate-900/60 text-xs text-slate-300">
            <div
              className={`w-2 h-2 rounded-full ${
                healthStatus === "ok"
                  ? "bg-emerald-400 animate-pulse"
                  : healthStatus === "degraded"
                  ? "bg-amber-400"
                  : "bg-rose-500"
              }`}
            />
            <span className="text-[11px] text-slate-400">
              Core: <strong className="text-slate-200 uppercase">{healthStatus}</strong>
            </span>
          </div>

          {/* Compute Units (CU) FinOps Indicator */}
          <div className="hidden xl:flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-slate-800 bg-slate-900/60 text-xs text-slate-300">
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            <span className="text-[11px] text-slate-400">
              CU Quota: <span className="text-emerald-400 font-mono font-semibold">98.4% Available</span>
            </span>
          </div>

          {/* Keyboard Shortcuts Trigger */}
          <button
            onClick={() => setShortcutsOpen(true)}
            className="p-2 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent hover:border-slate-800 transition-colors"
            title="Keyboard Shortcuts (?)"
          >
            <HelpCircle className="w-4 h-4" />
          </button>

          {/* Language / Locale Switcher */}
          <LocaleSwitcher />

          {/* User Menu */}
          <UserMenu />
        </div>
      </header>

      <ShortcutsModal isOpen={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
      <CommandPalette
        isOpen={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        onOpenSettings={onOpenSettings}
      />
    </>
  );
}
