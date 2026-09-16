"use client";

import React from "react";
import { Modal } from "./Modal";
import { Command } from "lucide-react";

export interface ShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ShortcutsModal({ isOpen, onClose }: ShortcutsModalProps) {
  const shortcuts = [
    { key: "⌘ + K", description: "Global search / command palette" },
    { key: "⌘ + Enter", description: "Submit query in chat" },
    { key: "⌘ + N", description: "Start a new chat session" },
    { key: "Esc", description: "Close open modal or slide-out viewer" },
    { key: "?", description: "Show keyboard shortcuts cheatsheet" },
  ];

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex items-center gap-2">
          <Command className="w-4 h-4 text-sky-400" />
          <span>Keyboard Shortcuts</span>
        </div>
      }
      description="Quick navigation and power commands across TitanRAG"
      maxWidth="md"
    >
      <div className="divide-y divide-slate-800">
        {shortcuts.map((s) => (
          <div key={s.key} className="flex items-center justify-between py-2.5 first:pt-0 last:pb-0">
            <span className="text-xs text-slate-300">{s.description}</span>
            <kbd className="px-2 py-1 text-[11px] font-mono font-bold text-slate-200 bg-slate-800 border border-slate-700/80 rounded-md shadow-sm">
              {s.key}
            </kbd>
          </div>
        ))}
      </div>
    </Modal>
  );
}
