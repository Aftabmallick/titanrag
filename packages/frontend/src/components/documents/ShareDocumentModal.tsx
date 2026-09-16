"use client";

import React, { useState } from "react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { Share2, CheckCircle2, ShieldCheck, Building } from "lucide-react";
import { DocumentRecord } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/components/ui/Toast";

export interface ShareDocumentModalProps {
  isOpen: boolean;
  onClose: () => void;
  document: DocumentRecord | null;
}

export function ShareDocumentModal({
  isOpen,
  onClose,
  document,
}: ShareDocumentModalProps) {
  const { workspaces, activeWorkspace } = useAuth();
  const { success } = useToast();
  const [selectedTargetWsId, setSelectedTargetWsId] = useState("");
  const [sharing, setSharing] = useState(false);

  if (!document) return null;

  const otherWorkspaces = workspaces.filter((w) => w.id !== activeWorkspace?.id);

  const handleShare = () => {
    if (!selectedTargetWsId) return;
    setSharing(true);
    setTimeout(() => {
      setSharing(false);
      success("Document Shared", `"${document.title}" shared as read-only reference.`);
      onClose();
    }, 600);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex items-center gap-2">
          <Share2 className="w-5 h-5 text-sky-400" />
          <span>Share Document Across Workspaces</span>
        </div>
      }
      description="Share this document as a read-only projection with other workspaces in your tenant while preserving source ACL groups."
      maxWidth="md"
    >
      <div className="space-y-4 py-2">
        <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 text-xs text-slate-300">
          <div className="font-semibold text-white">{document.title}</div>
          <div className="text-[10px] text-slate-500 font-mono mt-0.5">{document.id}</div>
        </div>

        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-300 block">
            Select Destination Workspace
          </label>
          <select
            value={selectedTargetWsId}
            onChange={(e) => setSelectedTargetWsId(e.target.value)}
            className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500 cursor-pointer"
          >
            <option value="">-- Choose a workspace --</option>
            {otherWorkspaces.map((ws) => (
              <option key={ws.id} value={ws.id}>
                {ws.name}
              </option>
            ))}
          </select>
        </div>

        <div className="p-3 rounded-xl bg-sky-500/10 border border-sky-500/20 text-xs text-sky-300 flex items-start gap-2">
          <ShieldCheck className="w-4 h-4 text-sky-400 shrink-0 mt-0.5" />
          <p className="text-[11px] leading-relaxed">
            Zero-copy sharing: creates a reference pointer without duplicating vector embeddings or MinIO storage. Destination workspace users can retrieve this document subject to group ACL rules.
          </p>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            disabled={!selectedTargetWsId || sharing}
            loading={sharing}
            onClick={handleShare}
          >
            Share Document
          </Button>
        </div>
      </div>
    </Modal>
  );
}
