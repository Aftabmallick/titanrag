"use client";

import React, { useState } from "react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Sparkles, Building, UploadCloud, MessageSquare, CheckCircle2 } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import { StepWorkspace } from "./StepWorkspace";
import { StepDocuments } from "./StepDocuments";
import { StepAskAi } from "./StepAskAi";

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

        {/* Step 1: Workspace */}
        {step === 1 && (
          <StepWorkspace
            workspaceName={workspaceName}
            setWorkspaceName={setWorkspaceName}
            activeWorkspaceName={activeWorkspace?.name}
            loading={loading}
            onNext={handleCreateWorkspace}
          />
        )}

        {/* Step 2: Documents */}
        {step === 2 && (
          <StepDocuments
            onBack={() => setStep(1)}
            onNext={() => setStep(3)}
          />
        )}

        {/* Step 3: Ask AI */}
        {step === 3 && (
          <StepAskAi
            onBack={() => setStep(2)}
            onFinish={handleFinish}
          />
        )}
      </div>
    </Modal>
  );
}
