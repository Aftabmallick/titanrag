"use client";

import React from "react";

interface KeyboardShortcut {
  keys: string[];
  description: string;
}

const SHORTCUTS: KeyboardShortcut[] = [
  { keys: ["⌘", "K"], description: "Open search / command palette" },
  { keys: ["⌘", "N"], description: "New chat session" },
  { keys: ["⌘", "Enter"], description: "Send message" },
  { keys: ["⌘", "⇧", "U"], description: "Upload document" },
  { keys: ["Esc"], description: "Close modal or drawer" },
  { keys: ["?"], description: "Toggle this shortcuts panel" },
];

interface KeyboardShortcutsHelpProps {
  isOpen: boolean;
  onClose: () => void;
}

export function KeyboardShortcutsHelp({ isOpen, onClose }: KeyboardShortcutsHelpProps) {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="shortcuts-title"
    >
      <div
        className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />
      <div className="relative glass-card rounded-2xl border border-slate-700/60 w-full max-w-sm mx-4 p-6 shadow-2xl">
        <h2
          id="shortcuts-title"
          className="text-base font-bold text-slate-100 mb-5 flex items-center gap-2"
        >
          <span className="text-lg">⌨️</span>
          Keyboard Shortcuts
        </h2>
        <div className="space-y-2.5">
          {SHORTCUTS.map(({ keys, description }) => (
            <div key={description} className="flex items-center justify-between">
              <span className="text-sm text-slate-400">{description}</span>
              <div className="flex items-center gap-1">
                {keys.map((k, i) => (
                  <kbd
                    key={i}
                    className="px-2 py-0.5 text-xs font-mono font-semibold text-slate-300 bg-slate-700/80 border border-slate-600/60 rounded-md shadow-sm"
                  >
                    {k}
                  </kbd>
                ))}
              </div>
            </div>
          ))}
        </div>
        <button
          id="shortcuts-close-btn"
          onClick={onClose}
          className="mt-6 w-full py-2 rounded-xl text-sm font-medium text-slate-400 border border-slate-700/60 hover:bg-slate-800/60 transition-all"
          aria-label="Close keyboard shortcuts help"
        >
          Close
        </button>
      </div>
    </div>
  );
}
