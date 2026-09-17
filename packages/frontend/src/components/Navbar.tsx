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
import { WorkspaceSwitcher } from "@/components/layout/WorkspaceSwitcher";

export function Navbar() {
  const { user, demoLogin, logout } = useAuth();
  const [backendStatus, setBackendStatus] = useState<"online" | "offline" | "checking">("checking");

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch("/api/v1/health/live");
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

            {/* Workspace Switcher */}
            <WorkspaceSwitcher />

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
    </>
  );
}
