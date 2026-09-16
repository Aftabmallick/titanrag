"use client";

import React, { useState } from "react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { AlertTriangle, Check, ShieldAlert, FileSearch, MessageSquareQuote } from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";

export interface FeedbackModalProps {
  isOpen: boolean;
  onClose: () => void;
  workspaceId: string | undefined;
  messageId: string;
}

const ISSUE_CATEGORIES = [
  { id: "hallucination", label: "Ungrounded or Hallucinated Claim", icon: ShieldAlert },
  { id: "bad_citation", label: "Inaccurate Citation / Wrong Source", icon: FileSearch },
  { id: "incomplete", label: "Incomplete or Missing Context", icon: MessageSquareQuote },
  { id: "formatting", label: "Formatting or Tone Issue", icon: AlertTriangle },
];

export function FeedbackModal({
  isOpen,
  onClose,
  workspaceId,
  messageId,
}: FeedbackModalProps) {
  const { success, error } = useToast();
  const [selectedCategory, setSelectedCategory] = useState<string>("hallucination");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!workspaceId) return;

    setSubmitting(true);
    try {
      await api.submitFeedback(workspaceId, messageId, "down");
      success("Report Recorded", "Thank you for helping harden our grounding guardrails.");
      onClose();
      setComment("");
    } catch (err: any) {
      error("Failed to Submit Feedback", err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Report Response Issue"
      description="Flag grounding discrepancies, citation mismatches, or reasoning flaws to improve enterprise alignment."
      maxWidth="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Category Picker */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-300">Issue Category</label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {ISSUE_CATEGORIES.map((cat) => {
              const Icon = cat.icon;
              const isSelected = selectedCategory === cat.id;

              return (
                <button
                  type="button"
                  key={cat.id}
                  onClick={() => setSelectedCategory(cat.id)}
                  className={`flex items-start gap-2.5 p-2.5 rounded-xl border text-left transition-all ${
                    isSelected
                      ? "bg-sky-500/10 border-sky-500/40 text-white"
                      : "bg-slate-900/60 border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-850"
                  }`}
                >
                  <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${isSelected ? "text-sky-400" : "text-slate-500"}`} />
                  <span className="text-xs font-medium leading-tight">{cat.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Details Textarea */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-300">
            Additional Details <span className="text-slate-500 font-normal">(Optional)</span>
          </label>
          <textarea
            rows={3}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Explain what was inaccurate or unverified..."
            className="w-full rounded-xl border border-slate-800 bg-slate-950/80 p-3 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500"
          />
        </div>

        {/* Modal Actions */}
        <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
          <Button variant="ghost" size="sm" type="button" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button
            variant="danger"
            size="sm"
            type="submit"
            loading={submitting}
            icon={<AlertTriangle className="w-3.5 h-3.5" />}
          >
            Submit Report
          </Button>
        </div>
      </form>
    </Modal>
  );
}
