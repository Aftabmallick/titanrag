"use client";

import React, { useState } from "react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: any[]) {
  return twMerge(clsx(inputs));
}

export interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactNode;
  side?: "top" | "bottom" | "left" | "right";
  className?: string;
}

export function Tooltip({
  content,
  children,
  side = "top",
  className,
}: TooltipProps) {
  const [visible, setVisible] = useState(false);

  const getPositionClasses = () => {
    switch (side) {
      case "bottom":
        return "top-full left-1/2 -translate-x-1/2 mt-1.5";
      case "left":
        return "right-full top-1/2 -translate-y-1/2 mr-1.5";
      case "right":
        return "left-full top-1/2 -translate-y-1/2 ml-1.5";
      case "top":
      default:
        return "bottom-full left-1/2 -translate-x-1/2 mb-1.5";
    }
  };

  return (
    <div
      className={cn("relative inline-flex items-center", className)}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      {children}
      {visible && (
        <div
          role="tooltip"
          className={cn(
            "absolute z-50 px-2 py-1 rounded-md bg-slate-900 border border-slate-700 text-[11px] font-medium text-slate-200 shadow-xl whitespace-nowrap pointer-events-none animate-in fade-in zoom-in-95 duration-100",
            getPositionClasses()
          )}
        >
          {content}
        </div>
      )}
    </div>
  );
}
