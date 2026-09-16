"use client";

import React, { useState } from "react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Sparkles, Building, UploadCloud, MessageSquare, CheckCircle2 } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";

export interface OnboardingModalProps {
  isOpen: boolean;
  onClose: () => void;
  onComplete: () => void;
}

export function OnboardingModal({ isOpen, onClose, onComplete }: OnboardingModalProps) {
  const { activeWorkspace, refreshWorkspaces } = useAuth();
  const { success, error } = useToast();

  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [workspaceName, setWorkspaceName] = useState("");
  const [loading, setLoading] = useState(false);

  const handleCreateWorkspace = async () => {
    if (!workspaceName.trim()) {
      setStep(2);
      return;
    }
    setLoading(true);
    try {
      await api.createWorkspace(workspaceName.trim());
      await refreshWorkspaces();
      success("Workspace Created", `Workspace "${workspaceName}" is active.`);
      setStep(2);
    } catch (err: any) {
      error("Could not create workspace", err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFinish = async () => {
    try {
      await api.completeOnboarding();
    } catch {
      // ignore
    }
    localStorage.setItem("titan_onboarding_done", "true");
    onComplete();
    onClose();
    success("Onboarding Completed!", "You are ready to search and chat with documents.");
  };

  const handleDismiss = () => {
    localStorage.setItem("titan_onboarding_done", "true");
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleDismiss}
      maxWidth="lg"
      title={
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-sky-400" />
          <span>Welcome to TitanRAG Enterprise</span>
        </div>
      }
      description="Let's get your enterprise RAG environment configured in 3 simple steps."
    >
      <div className="space-y-6 py-2">
        {/* Step Indicator */}
        <div className="grid grid-cols-3 gap-2 border-b border-slate-800 pb-4 text-center">
          <div
            className={`flex items-center justify-center gap-2 text-xs font-semibold py-1.5 rounded-lg ${
              step === 1 ? "bg-sky-500/10 text-sky-400 border border-sky-500/30" : "text-slate-500"
            }`}
          >
            <Building className="w-3.5 h-3.5" />
            <span>1. Workspace</span>
          </div>
          <div
            className={`flex items-center justify-center gap-2 text-xs font-semibold py-1.5 rounded-lg ${
              step === 2 ? "bg-sky-500/10 text-sky-400 border border-sky-500/30" : "text-slate-500"
            }`}
          >
            <UploadCloud className="w-3.5 h-3.5" />
            <span>2. Documents</span>
          </div>
          <div
            className={`flex items-center justify-center gap-2 text-xs font-semibold py-1.5 rounded-lg ${
              step === 3 ? "bg-sky-500/10 text-sky-400 border border-sky-500/30" : "text-slate-500"
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            <span>3. Ask AI</span>
          </div>
        </div>

        {/* Step 1 Content */}
        {step === 1 && (
          <div className="space-y-4">
            <div className="space-y-1">
              <h4 className="text-sm font-bold text-slate-100">Set Up Your First Workspace</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Workspaces are isolated knowledge domains with dedicated ACL access lists, vector
                payload filters, and custom RAG tuning parameters.
              </p>
            </div>
            <Input
              label="Workspace Name"
              placeholder={activeWorkspace?.name || "Legal & Compliance"}
              value={workspaceName}
              onChange={(e) => setWorkspaceName(e.target.value)}
            />
            <div className="flex justify-between items-center pt-2">
              <button
                onClick={() => setStep(2)}
                className="text-xs text-slate-500 hover:text-slate-300 font-medium"
              >
                Skip (use default workspace)
              </button>
              <Button variant="primary" size="sm" loading={loading} onClick={handleCreateWorkspace}>
                Continue to Step 2
              </Button>
            </div>
          </div>
        )}

        {/* Step 2 Content */}
        {step === 2 && (
          <div className="space-y-4">
            <div className="space-y-1">
              <h4 className="text-sm font-bold text-slate-100">Add Enterprise Documents</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Upload PDF, DOCX, CSV, or TXT files. Documents undergo Docling structural parsing,
                PII entity redaction, and hierarchical chunking.
              </p>
            </div>
            <div className="p-6 rounded-xl border border-dashed border-slate-700 bg-slate-900/40 text-center space-y-2">
              <UploadCloud className="w-8 h-8 text-sky-400 mx-auto" />
              <p className="text-xs text-slate-300 font-medium">
                You can upload files anytime via the Documents console
              </p>
              <p className="text-[11px] text-slate-500">
                Supports native PDFs, scanned documents with OCR, and SaaS connectors.
              </p>
            </div>
            <div className="flex justify-between items-center pt-2">
              <button
                onClick={() => setStep(1)}
                className="text-xs text-slate-500 hover:text-slate-300 font-medium"
              >
                Back
              </button>
              <Button variant="primary" size="sm" onClick={() => setStep(3)}>
                Continue to Step 3
              </Button>
            </div>
          </div>
        )}

        {/* Step 3 Content */}
        {step === 3 && (
          <div className="space-y-4">
            <div className="space-y-1">
              <h4 className="text-sm font-bold text-slate-100">Experience Grounded RAG Generation</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Ask questions across your documents. TitanRAG uses hybrid dense + sparse retrieval,
                cross-encoder reranking, and post-generation NLI claim verification.
              </p>
            </div>
            <div className="space-y-2">
              <div className="p-3 rounded-xl bg-slate-800/60 border border-slate-700/60 text-xs text-slate-300 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Clickable inline citations link directly to verified PDF pages.</span>
              </div>
              <div className="p-3 rounded-xl bg-slate-800/60 border border-slate-700/60 text-xs text-slate-300 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Sub-1.8s Fast-Path TTFT via in-process ONNX classifier.</span>
              </div>
            </div>
            <div className="flex justify-between items-center pt-4">
              <button
                onClick={() => setStep(2)}
                className="text-xs text-slate-500 hover:text-slate-300 font-medium"
              >
                Back
              </button>
              <Button variant="primary" size="sm" onClick={handleFinish}>
                Start Using TitanRAG
              </Button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
