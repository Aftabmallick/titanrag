"use client";

import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle,
  Info,
  X,
  ExternalLink,
} from "lucide-react";

interface Announcement {
  id: string;
  title: string;
  body: string;
  severity: string;
  action_url: string | null;
  action_label: string | null;
  expires_at: string | null;
}

const SEVERITY_CONFIG = {
  INFO: {
    icon: <Info className="w-4 h-4 flex-shrink-0" />,
    className:
      "bg-indigo-950/60 border-indigo-800/50 text-indigo-200",
    iconClass: "text-indigo-400",
    closeClass: "text-indigo-400 hover:text-indigo-200",
  },
  WARNING: {
    icon: <AlertTriangle className="w-4 h-4 flex-shrink-0" />,
    className:
      "bg-amber-950/60 border-amber-800/50 text-amber-200",
    iconClass: "text-amber-400",
    closeClass: "text-amber-400 hover:text-amber-200",
  },
  CRITICAL: {
    icon: <AlertTriangle className="w-4 h-4 flex-shrink-0" />,
    className:
      "bg-red-950/60 border-red-800/50 text-red-200",
    iconClass: "text-red-400",
    closeClass: "text-red-400 hover:text-red-200",
  },
};

export function AnnouncementBanner() {
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  useEffect(() => {
    // Load dismissed IDs from sessionStorage
    const saved = sessionStorage.getItem("titan_dismissed_announcements");
    if (saved) {
      try {
        setDismissed(new Set(JSON.parse(saved)));
      } catch {
        // ignore
      }
    }

    // Fetch active announcements
    const token = localStorage.getItem("titan_token");
    if (!token) return;

    fetch("/api/v1/announcements", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => setAnnouncements(data || []))
      .catch(() => {});
  }, []);

  function dismiss(id: string) {
    const next = new Set(dismissed);
    next.add(id);
    setDismissed(next);
    sessionStorage.setItem(
      "titan_dismissed_announcements",
      JSON.stringify(Array.from(next))
    );
  }

  const visible = announcements.filter((a) => !dismissed.has(a.id));

  if (visible.length === 0) return null;

  return (
    <div
      className="flex flex-col gap-1.5"
      role="region"
      aria-label="System announcements"
    >
      {visible.map((ann) => {
        const cfg =
          SEVERITY_CONFIG[ann.severity as keyof typeof SEVERITY_CONFIG] ||
          SEVERITY_CONFIG.INFO;

        return (
          <div
            key={ann.id}
            role="alert"
            aria-live="polite"
            className={`flex items-start gap-3 px-4 py-3 border rounded-xl text-sm transition-all duration-300 ${cfg.className}`}
            style={{ animation: "fadeInSlide 0.3s ease-out" }}
          >
            <span className={cfg.iconClass}>{cfg.icon}</span>
            <div className="flex-1 min-w-0">
              <span className="font-semibold">{ann.title}</span>
              {ann.body && (
                <span className="ml-1.5 opacity-80">{ann.body}</span>
              )}
              {ann.action_url && (
                <a
                  href={ann.action_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 ml-2 underline hover:opacity-80 transition-opacity text-xs"
                  aria-label={ann.action_label || "Learn more"}
                >
                  {ann.action_label || "Learn more"}
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
            <button
              id={`dismiss-announcement-${ann.id}`}
              onClick={() => dismiss(ann.id)}
              className={`flex-shrink-0 p-0.5 rounded transition-colors ${cfg.closeClass}`}
              aria-label={`Dismiss announcement: ${ann.title}`}
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
