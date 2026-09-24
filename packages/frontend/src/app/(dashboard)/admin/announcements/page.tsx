"use client";

import React, { useState } from "react";
import {
  Bell,
  Plus,
  AlertTriangle,
  Info,
  CheckCircle,
  Trash2,
  Calendar,
  ExternalLink,
} from "lucide-react";
import { AnnouncementBanner } from "@/components/admin/AnnouncementBanner";

interface AnnouncementItem {
  id: string;
  title: string;
  body: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  is_active: boolean;
  action_url?: string;
  action_label?: string;
  expires_at?: string;
  created_at: string;
}

export default function AnnouncementsAdminPage() {
  const [announcements, setAnnouncements] = useState<AnnouncementItem[]>([
    {
      id: "ann-01",
      title: "Scheduled Maintenance Window",
      body: "Vector indexing workers will undergo scheduled database maintenance on Sunday at 02:00 UTC. Search queries will remain fully accessible.",
      severity: "WARNING",
      is_active: true,
      action_url: "https://status.titanrag.ai",
      action_label: "Status Page",
      expires_at: "2026-10-01T00:00:00Z",
      created_at: "2026-09-24T12:00:00Z",
    },
    {
      id: "ann-02",
      title: "TitanRAG V2.0 GA Released!",
      body: "Explore multi-framework evaluations, white-label portals, and batch APIs in production.",
      severity: "INFO",
      is_active: true,
      action_url: "/docs",
      action_label: "Read Docs",
      created_at: "2026-09-24T08:00:00Z",
    },
  ]);

  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [severity, setSeverity] = useState<"INFO" | "WARNING" | "CRITICAL">("INFO");
  const [actionUrl, setActionUrl] = useState("");
  const [actionLabel, setActionLabel] = useState("");

  const handleCreate = () => {
    if (!title || !body) return;
    const newAnn: AnnouncementItem = {
      id: `ann-${Date.now()}`,
      title,
      body,
      severity,
      is_active: true,
      action_url: actionUrl || undefined,
      action_label: actionLabel || undefined,
      created_at: new Date().toISOString(),
    };
    setAnnouncements([newAnn, ...announcements]);
    setCreateModalOpen(false);
    setTitle("");
    setBody("");
    setActionUrl("");
    setActionLabel("");
  };

  const handleDelete = (id: string) => {
    setAnnouncements(announcements.filter((a) => a.id !== id));
  };

  return (
    <div className="space-y-8 p-6 lg:p-10 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2.5">
            <Bell className="w-7 h-7 text-indigo-400" />
            System Broadcast Announcements
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Broadcast platform-wide notices and maintenance alerts to all tenant dashboards.
          </p>
        </div>

        <button
          onClick={() => setCreateModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium shadow-lg shadow-indigo-600/30 transition-all self-start md:self-auto"
        >
          <Plus className="w-4 h-4" />
          Create Announcement
        </button>
      </div>

      {/* Live Preview */}
      <div className="space-y-3">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Live User Banner Preview
        </h2>
        <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
          <AnnouncementBanner />
        </div>
      </div>

      {/* Announcements List */}
      <div className="rounded-xl border border-slate-800 bg-slate-950/60 shadow-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-800/80 bg-slate-900/50">
          <h3 className="text-sm font-semibold text-slate-200">Active & Past Announcements</h3>
        </div>

        <div className="divide-y divide-slate-800/60">
          {announcements.map((ann) => (
            <div key={ann.id} className="p-6 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-slate-900/30">
              <div className="space-y-1.5 max-w-2xl">
                <div className="flex items-center gap-2.5">
                  <span
                    className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
                      ann.severity === "CRITICAL"
                        ? "bg-rose-950/60 text-rose-300 border-rose-800/60"
                        : ann.severity === "WARNING"
                        ? "bg-amber-950/60 text-amber-300 border-amber-800/60"
                        : "bg-indigo-950/60 text-indigo-300 border-indigo-800/60"
                    }`}
                  >
                    {ann.severity}
                  </span>
                  <span className="font-medium text-slate-100">{ann.title}</span>
                </div>
                <p className="text-sm text-slate-300">{ann.body}</p>
                {ann.action_url && (
                  <a
                    href={ann.action_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300"
                  >
                    {ann.action_label || "Learn More"}
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>

              <div className="flex items-center gap-4 self-end md:self-auto">
                <button
                  onClick={() => handleDelete(ann.id)}
                  className="p-2 text-slate-400 hover:text-rose-400 rounded-lg hover:bg-slate-800 transition-colors"
                  aria-label="Delete announcement"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Create Modal */}
      {createModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <h3 className="text-lg font-semibold text-slate-100">
              Create System Announcement
            </h3>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Title
                </label>
                <input
                  type="text"
                  placeholder="e.g. Scheduled Maintenance"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Severity
                </label>
                <select
                  value={severity}
                  onChange={(e) => setSeverity(e.target.value as any)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="INFO">INFO (Blue/Indigo)</option>
                  <option value="WARNING">WARNING (Amber)</option>
                  <option value="CRITICAL">CRITICAL (Red)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Message Body
                </label>
                <textarea
                  rows={3}
                  placeholder="Enter details of the broadcast..."
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Action URL (Optional)
                  </label>
                  <input
                    type="text"
                    placeholder="https://..."
                    value={actionUrl}
                    onChange={(e) => setActionUrl(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Action Label
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. View Status"
                    value={actionLabel}
                    onChange={(e) => setActionLabel(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
              <button
                onClick={() => setCreateModalOpen(false)}
                className="px-4 py-2 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                className="px-4 py-2 rounded-lg text-xs font-medium bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/30"
              >
                Publish Broadcast
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
