"use client";

import React from "react";
import { motion } from "framer-motion";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: any[]) {
  return twMerge(clsx(inputs));
}

export interface TabOption<T extends string = string> {
  id: T;
  label: string;
  icon?: React.ReactNode;
  badge?: string | number;
}

export interface TabsProps<T extends string = string> {
  tabs: TabOption<T>[];
  activeTab: T;
  onChange: (id: T) => void;
  className?: string;
  variant?: "pills" | "underline";
}

export function Tabs<T extends string = string>({
  tabs,
  activeTab,
  onChange,
  className,
  variant = "pills",
}: TabsProps<T>) {
  if (variant === "underline") {
    return (
      <div className={cn("flex items-center gap-6 border-b border-slate-800", className)}>
        {tabs.map((tab) => {
          const isActive = tab.id === activeTab;
          return (
            <button
              key={tab.id}
              onClick={() => onChange(tab.id)}
              className={cn(
                "relative pb-3 text-xs font-semibold tracking-wide transition-colors flex items-center gap-2",
                isActive ? "text-sky-400" : "text-slate-400 hover:text-slate-200"
              )}
            >
              {tab.icon && <span className="shrink-0">{tab.icon}</span>}
              <span>{tab.label}</span>
              {tab.badge !== undefined && (
                <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-300">
                  {tab.badge}
                </span>
              )}
              {isActive && (
                <motion.div
                  layoutId="activeTabUnderline"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-sky-400 to-indigo-500 rounded-full"
                  transition={{ type: "spring", damping: 30, stiffness: 350 }}
                />
              )}
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div
      className={cn(
        "inline-flex items-center p-1 rounded-xl bg-slate-900/90 border border-slate-800 gap-1",
        className
      )}
    >
      {tabs.map((tab) => {
        const isActive = tab.id === activeTab;
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={cn(
              "relative px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center gap-2 z-10",
              isActive ? "text-white" : "text-slate-400 hover:text-slate-200"
            )}
          >
            {isActive && (
              <motion.div
                layoutId="activeTabPill"
                className="absolute inset-0 bg-slate-800 border border-slate-700/80 rounded-lg shadow-sm -z-10"
                transition={{ type: "spring", damping: 25, stiffness: 300 }}
              />
            )}
            {tab.icon && <span className="shrink-0">{tab.icon}</span>}
            <span>{tab.label}</span>
            {tab.badge !== undefined && (
              <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-700/50 text-slate-300">
                {tab.badge}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
