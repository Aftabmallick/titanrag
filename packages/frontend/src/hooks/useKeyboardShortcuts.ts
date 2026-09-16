"use client";

import { useEffect } from "react";

export interface ShortcutHandlers {
  onNewChat?: () => void;
  onOpenSearch?: () => void;
  onOpenSettings?: () => void;
  onOpenShortcuts?: () => void;
  onEscape?: () => void;
}

export function useKeyboardShortcuts({
  onNewChat,
  onOpenSearch,
  onOpenSettings,
  onOpenShortcuts,
  onEscape,
}: ShortcutHandlers) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if user is typing inside an input or textarea
      const target = e.target as HTMLElement;
      const isInput =
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable;

      if (e.key === "Escape") {
        if (onEscape) onEscape();
        return;
      }

      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (onOpenSearch) onOpenSearch();
        return;
      }

      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "n") {
        e.preventDefault();
        if (onNewChat) onNewChat();
        return;
      }

      if (!isInput && e.key === "?") {
        e.preventDefault();
        if (onOpenShortcuts) onOpenShortcuts();
        return;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onNewChat, onOpenSearch, onOpenSettings, onOpenShortcuts, onEscape]);
}
