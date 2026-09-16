"use client";

import React, { useState, useRef, useEffect } from "react";
import { User, LogOut, Sun, Moon, Laptop, Shield } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { Badge } from "@/components/ui/Badge";
import { LocaleSwitcher } from "./LocaleSwitcher";

export function UserMenu() {
  const { user, logout } = useAuth();
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (!user) return null;

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 p-1.5 rounded-xl border border-slate-800 bg-slate-900/80 hover:bg-slate-850 transition-colors focus:outline-none focus:ring-2 focus:ring-sky-500/20"
      >
        <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center text-white text-xs font-bold shadow-sm">
          {user.full_name ? user.full_name.charAt(0).toUpperCase() : "U"}
        </div>
        <span className="hidden md:inline text-xs font-medium text-slate-200 pr-1 max-w-[120px] truncate">
          {user.full_name || user.email}
        </span>
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-64 rounded-2xl bg-slate-900 border border-slate-800 shadow-2xl z-50 p-2 space-y-2">
          <div className="p-3 bg-slate-950/60 rounded-xl space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-100 truncate">{user.full_name}</span>
              <Badge variant="primary" size="xs">
                {user.role || "Admin"}
              </Badge>
            </div>
            <p className="text-[11px] text-slate-400 truncate">{user.email}</p>
          </div>

          <div className="pt-1 border-t border-slate-800/80 space-y-1">
            {/* Theme switcher */}
            <div className="px-3 py-1.5 flex items-center justify-between text-xs text-slate-300">
              <span className="flex items-center gap-2">
                {resolvedTheme === "dark" ? <Moon className="w-3.5 h-3.5" /> : <Sun className="w-3.5 h-3.5" />}
                <span>Theme</span>
              </span>
              <div className="flex items-center gap-1 bg-slate-800 p-0.5 rounded-lg">
                <button
                  onClick={() => setTheme("light")}
                  className={`p-1 rounded-md text-[10px] ${theme === "light" ? "bg-slate-700 text-white" : "text-slate-400"}`}
                  title="Light Theme"
                >
                  <Sun className="w-3 h-3" />
                </button>
                <button
                  onClick={() => setTheme("dark")}
                  className={`p-1 rounded-md text-[10px] ${theme === "dark" ? "bg-slate-700 text-white" : "text-slate-400"}`}
                  title="Dark Theme"
                >
                  <Moon className="w-3 h-3" />
                </button>
                <button
                  onClick={() => setTheme("system")}
                  className={`p-1 rounded-md text-[10px] ${theme === "system" ? "bg-slate-700 text-white" : "text-slate-400"}`}
                  title="System Theme"
                >
                  <Laptop className="w-3 h-3" />
                </button>
              </div>
            </div>

            {/* Language Selector Row */}
            <div className="px-3 py-1.5 flex items-center justify-between text-xs text-slate-300">
              <span className="flex items-center gap-2">
                <span>🌐</span>
                <span>Language</span>
              </span>
              <LocaleSwitcher />
            </div>

            <button
              onClick={() => {
                setIsOpen(false);
                logout();
              }}
              className="w-full flex items-center gap-2 px-3 py-2 text-xs font-semibold text-rose-400 hover:bg-rose-500/10 rounded-xl transition-colors text-left"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
