"use client";

import React, { useState } from "react";
import {
  FolderSync,
  CheckCircle2,
  RefreshCw,
  ExternalLink,
  Sliders,
  Clock,
  Shield,
  AlertCircle,
  Database,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { useToast } from "@/components/ui/Toast";
import { SyncLogTable } from "./SyncLogTable";

interface ConnectorItem {
  id: string;
  name: string;
  provider: "google_drive" | "sharepoint" | "confluence" | "notion";
  status: "connected" | "syncing" | "error" | "disconnected";
  lastSync: string | null;
  docsSynced: number;
  syncFrequency: string;
}

export function ConnectorConsole({ workspaceId }: { workspaceId: string | undefined }) {
  const { success, info } = useToast();

  const [connectors, setConnectors] = useState<ConnectorItem[]>([
    {
      id: "gdrive-1",
      name: "Google Drive",
      provider: "google_drive",
      status: "connected",
      lastSync: "12 minutes ago",
      docsSynced: 42,
      syncFrequency: "Every 15m",
    },
    {
      id: "sharepoint-1",
      name: "Microsoft SharePoint",
      provider: "sharepoint",
      status: "disconnected",
      lastSync: null,
      docsSynced: 0,
      syncFrequency: "Hourly",
    },
    {
      id: "confluence-1",
      name: "Atlassian Confluence",
      provider: "confluence",
      status: "connected",
      lastSync: "1 hour ago",
      docsSynced: 128,
      syncFrequency: "Daily",
    },
    {
      id: "notion-1",
      name: "Notion Workspace",
      provider: "notion",
      status: "disconnected",
      lastSync: null,
      docsSynced: 0,
      syncFrequency: "Real-time CDC",
    },
  ]);

  const [configModalConnector, setConfigModalConnector] = useState<ConnectorItem | null>(null);
  const [syncingId, setSyncingId] = useState<string | null>(null);

  const handleSyncNow = (id: string, name: string) => {
    setSyncingId(id);
    info("Delta Sync Triggered", `Polling change tokens for ${name}...`);

    setTimeout(() => {
      setSyncingId(null);
      setConnectors((prev) =>
        prev.map((c) =>
          c.id === id ? { ...c, lastSync: "Just now", docsSynced: c.docsSynced + 3 } : c
        )
      );
      success("Sync Complete", `${name} delta changes committed to Qdrant outbox.`);
    }, 2000);
  };

  const handleConnect = (id: string) => {
    setConnectors((prev) =>
      prev.map((c) => (c.id === id ? { ...c, status: "connected", lastSync: "Just now" } : c))
    );
    success("Connector Authenticated", "OAuth credential exchange completed.");
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <FolderSync className="w-5 h-5 text-sky-400" />
            <span>Enterprise SaaS Data Connectors</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Continuous Change Data Capture (CDC) synchronization and source ACL permission mirroring.
          </p>
        </div>
      </div>

      {/* Connectors Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {connectors.map((connector) => {
          const isConnected = connector.status === "connected";
          const isSyncing = syncingId === connector.id;

          return (
            <div
              key={connector.id}
              className="p-5 rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-xl shadow-xl space-y-4"
            >
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Database className="w-4 h-4 text-sky-400" />
                    <h3 className="text-sm font-bold text-slate-100">{connector.name}</h3>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Source permission mirroring into Qdrant ACL groups
                  </p>
                </div>

                <Badge
                  variant={isConnected ? "success" : "neutral"}
                  size="xs"
                  pulse={isConnected}
                >
                  {isConnected ? "Active Sync" : "Not Connected"}
                </Badge>
              </div>

              {/* Stats row */}
              <div className="grid grid-cols-3 gap-2 p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 text-xs">
                <div>
                  <span className="text-[10px] text-slate-500 block">Synced Docs</span>
                  <span className="font-mono font-bold text-slate-200">{connector.docsSynced}</span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 block">Frequency</span>
                  <span className="font-semibold text-slate-300">{connector.syncFrequency}</span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 block">Last Delta</span>
                  <span className="text-slate-400 truncate block">
                    {connector.lastSync || "Never"}
                  </span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-between pt-1">
                {isConnected ? (
                  <>
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={<Sliders className="w-3.5 h-3.5" />}
                      onClick={() => setConfigModalConnector(connector)}
                    >
                      Configure
                    </Button>

                    <Button
                      variant="primary"
                      size="sm"
                      loading={isSyncing}
                      icon={<RefreshCw className="w-3.5 h-3.5" />}
                      onClick={() => handleSyncNow(connector.id, connector.name)}
                    >
                      Sync Now
                    </Button>
                  </>
                ) : (
                  <Button
                    variant="primary"
                    size="sm"
                    className="w-full"
                    icon={<ExternalLink className="w-3.5 h-3.5" />}
                    onClick={() => handleConnect(connector.id)}
                  >
                    Authenticate with OAuth
                  </Button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Sync Log Audit Trail */}
      <SyncLogTable />

      {/* Sync Configuration Modal */}
      {configModalConnector && (
        <Modal
          isOpen={!!configModalConnector}
          onClose={() => setConfigModalConnector(null)}
          title={`Configure ${configModalConnector.name}`}
          description="Adjust polling schedule, folder filtering, and ACL group mirroring."
        >
          <div className="space-y-4">
            <Input
              label="Folder / Site Path Filter"
              placeholder="/Engineering/Architecture-Docs"
              defaultValue="/Corporate/Confidential"
            />

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-300 block">
                Sync Frequency (Cron Expression)
              </label>
              <select className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200">
                <option>Every 15 minutes (*/15 * * * *)</option>
                <option>Hourly (0 * * * *)</option>
                <option>Daily at midnight (0 0 * * *)</option>
                <option>Real-Time Change Data Capture (Webhook)</option>
              </select>
            </div>

            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 text-xs text-slate-300 space-y-1">
              <div className="font-semibold text-emerald-400 flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Source System ACL Mirroring Enabled</span>
              </div>
              <p className="text-[11px] text-slate-400">
                Drive file permissions are automatically extracted and embedded into Qdrant chunk
                `acl_groups` payload pre-filters.
              </p>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setConfigModalConnector(null)}
              >
                Close
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  success("Configuration Saved", "Connector sync schedule updated.");
                  setConfigModalConnector(null);
                }}
              >
                Save Settings
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
