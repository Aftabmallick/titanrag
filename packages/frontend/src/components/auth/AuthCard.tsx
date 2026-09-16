"use client";

import React from "react";
import { ShieldCheck } from "lucide-react";
import Link from "next/link";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: any[]) {
  return twMerge(clsx(inputs));
}

export interface AuthCardProps {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  footerText: string;
  footerLinkText: string;
  footerLinkHref: string;
  className?: string;
}

export function AuthCard({
  title,
  subtitle,
  children,
  footerText,
  footerLinkText,
  footerLinkHref,
  className,
}: AuthCardProps) {
  return (
    <div className="min-h-screen w-full flex items-center justify-center p-4 sm:p-6 bg-slate-950 relative overflow-hidden">
      {/* Dynamic Background Mesh */}
      <div className="absolute top-1/4 -left-32 w-96 h-96 bg-sky-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 -right-32 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

      <div className={cn("w-full max-w-md space-y-6 relative z-10", className)}>
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-sky-500/30 bg-sky-500/10 text-sky-400 text-xs font-semibold uppercase tracking-wider">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>TitanRAG Enterprise Core</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            {title}
          </h1>
          <p className="text-xs sm:text-sm text-slate-400">{subtitle}</p>
        </div>

        {/* Form Card */}
        <div className="p-6 sm:p-8 rounded-2xl border border-slate-800 bg-slate-900/80 backdrop-blur-xl shadow-2xl shadow-black/40 space-y-5">
          {children}

          <div className="pt-4 border-t border-slate-800 text-center text-xs text-slate-400">
            {footerText}{" "}
            <Link
              href={footerLinkHref}
              className="font-semibold text-sky-400 hover:text-sky-300 transition-colors"
            >
              {footerLinkText}
            </Link>
          </div>
        </div>

        <div className="text-center text-[11px] text-slate-600">
          Protected by Row-Level Security (RLS) & Token-Bucket Rate Limiting
        </div>
      </div>
    </div>
  );
}
