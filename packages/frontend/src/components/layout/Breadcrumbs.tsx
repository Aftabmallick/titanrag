"use client";

import React from "react";
import Link from "next/link";
import { ChevronRight, Home, Sparkles, FileText, FolderSync, BarChart3, ShieldAlert } from "lucide-react";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";

export interface BreadcrumbsProps {
  currentTitle?: string;
}

export function Breadcrumbs({ currentTitle }: BreadcrumbsProps) {
  const pathname = usePathname();
  const { activeWorkspace } = useAuth();

  const getSectionInfo = () => {
    if (pathname.startsWith("/documents")) {
      return { name: "Knowledge Documents", href: "/documents", icon: FileText };
    }
    if (pathname.startsWith("/connectors")) {
      return { name: "SaaS Connectors", href: "/connectors", icon: FolderSync };
    }
    if (pathname.startsWith("/analytics")) {
      return { name: "Analytics & FinOps", href: "/analytics", icon: BarChart3 };
    }
    if (pathname.startsWith("/admin")) {
      return { name: "Platform Admin", href: "/admin", icon: ShieldAlert };
    }
    return { name: "Chat Workstation", href: "/", icon: Sparkles };
  };

  const section = getSectionInfo();
  const Icon = section.icon;

  return (
    <nav aria-label="Breadcrumbs" className="flex items-center gap-1.5 text-xs text-slate-400">
      {/* Workspace root */}
      <Link
        href="/"
        className="flex items-center gap-1 hover:text-slate-200 transition-colors max-w-[140px] truncate"
        title={activeWorkspace?.name || "Workspace"}
      >
        <Home className="w-3.5 h-3.5 shrink-0 text-slate-500" />
        <span className="font-semibold truncate">{activeWorkspace?.name || "Workspace"}</span>
      </Link>

      <ChevronRight className="w-3 h-3 text-slate-600 shrink-0" />

      {/* Current section */}
      <Link
        href={section.href}
        className={`flex items-center gap-1 transition-colors ${
          !currentTitle ? "text-sky-400 font-bold" : "hover:text-slate-200"
        }`}
      >
        <Icon className="w-3.5 h-3.5 shrink-0" />
        <span>{section.name}</span>
      </Link>

      {/* Sub-title if present */}
      {currentTitle && (
        <>
          <ChevronRight className="w-3 h-3 text-slate-600 shrink-0" />
          <span className="text-slate-200 font-medium truncate max-w-[200px]" title={currentTitle}>
            {currentTitle}
          </span>
        </>
      )}
    </nav>
  );
}
