"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { MessageSquare, FileText, FolderSync, BarChart3, Sliders } from "lucide-react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: any[]) {
  return twMerge(clsx(inputs));
}

export interface MobileNavProps {
  onOpenSettings: () => void;
}

export function MobileNav({ onOpenSettings }: MobileNavProps) {
  const pathname = usePathname();

  const navItems = [
    { label: "Chat", href: "/", icon: MessageSquare, exact: true },
    { label: "Docs", href: "/documents", icon: FileText },
    { label: "Sync", href: "/connectors", icon: FolderSync },
    { label: "Metrics", href: "/analytics", icon: BarChart3 },
  ];

  return (
    <nav
      aria-label="Mobile Navigation"
      className="md:hidden fixed bottom-0 left-0 right-0 z-40 h-16 bg-slate-950/90 border-t border-slate-800 backdrop-blur-xl px-2 flex items-center justify-around"
    >
      {navItems.map((item) => {
        const Icon = item.icon;
        const isActive = item.exact ? pathname === item.href : pathname.startsWith(item.href);

        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex flex-col items-center justify-center py-1 px-3 rounded-xl text-[10px] font-semibold transition-all",
              isActive
                ? "text-sky-400 bg-sky-500/10 border border-sky-500/20 shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            )}
          >
            <Icon className={cn("w-4 h-4 mb-0.5", isActive && "animate-pulse")} />
            <span>{item.label}</span>
          </Link>
        );
      })}

      <button
        type="button"
        onClick={onOpenSettings}
        className="flex flex-col items-center justify-center py-1 px-3 rounded-xl text-[10px] font-semibold text-slate-400 hover:text-slate-200 transition-colors"
      >
        <Sliders className="w-4 h-4 mb-0.5" />
        <span>RAG</span>
      </button>
    </nav>
  );
}
