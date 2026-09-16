"use client";

import React from "react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: any[]) {
  return twMerge(clsx(inputs));
}

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "primary" | "success" | "warning" | "error" | "neutral" | "outline";
  size?: "xs" | "sm" | "md";
  pulse?: boolean;
  icon?: React.ReactNode;
}

export function Badge({
  className,
  variant = "neutral",
  size = "sm",
  pulse = false,
  icon,
  children,
  ...props
}: BadgeProps) {
  const baseStyles = "inline-flex items-center font-medium rounded-full tracking-wide";

  const variants = {
    primary: "bg-sky-500/15 text-sky-400 border border-sky-500/30",
    success: "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30",
    warning: "bg-amber-500/15 text-amber-400 border border-amber-500/30",
    error: "bg-rose-500/15 text-rose-400 border border-rose-500/30",
    neutral: "bg-slate-800 text-slate-300 border border-slate-700/60",
    outline: "bg-transparent text-slate-400 border border-slate-700",
  };

  const sizes = {
    xs: "text-[10px] px-2 py-0.5 gap-1",
    sm: "text-xs px-2.5 py-0.5 gap-1.5",
    md: "text-xs px-3 py-1 gap-1.5",
  };

  const pulseColors = {
    primary: "bg-sky-400",
    success: "bg-emerald-400",
    warning: "bg-amber-400",
    error: "bg-rose-400",
    neutral: "bg-slate-400",
    outline: "bg-slate-400",
  };

  return (
    <span className={cn(baseStyles, variants[variant], sizes[size], className)} {...props}>
      {pulse && (
        <span className="relative flex h-1.5 w-1.5">
          <span
            className={cn(
              "animate-ping absolute inline-flex h-full w-full rounded-full opacity-75",
              pulseColors[variant]
            )}
          />
          <span className={cn("relative inline-flex rounded-full h-1.5 w-1.5", pulseColors[variant])} />
        </span>
      )}
      {icon && <span className="shrink-0">{icon}</span>}
      {children}
    </span>
  );
}
