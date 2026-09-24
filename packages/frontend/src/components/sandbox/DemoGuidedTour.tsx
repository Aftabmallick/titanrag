"use client";

import React, { useState, useEffect } from "react";
import {
  Sparkles,
  Search,
  FileText,
  Sliders,
  CheckCircle,
  X,
  ArrowRight,
  ArrowLeft,
} from "lucide-react";

interface Step {
  title: string;
  description: string;
  icon: React.ReactNode;
  hint: string;
}

const TOUR_STEPS: Step[] = [
  {
    title: "1. Ask Any Question",
    description:
      "Try asking about the pre-loaded legal contracts, engineering architectures, or research papers. The hybrid search engine combines vector and BM25/SPLADE retrieval.",
    icon: <Search className="w-6 h-6 text-indigo-400" />,
    hint: "Try: 'What are the termination clauses in the Master Services Agreement?'",
  },
  {
    title: "2. Inspect Verified Citations",
    description:
      "Every response includes exact chunk citations with confidence scores and PDF page highlights. Click any source pill to inspect the ground-truth text.",
    icon: <FileText className="w-6 h-6 text-emerald-400" />,
    hint: "Notice the green badge indicating 99.4% factual faithfulness.",
  },
  {
    title: "3. Upload Your Own Document",
    description:
      "Drop any PDF, Markdown, or DOCX into the upload drawer. Our Docling OCR and MinHash deduplication pipeline processes files in seconds.",
    icon: <Sparkles className="w-6 h-6 text-amber-400" />,
    hint: "Sandbox allows up to 5 uploads with 24-hour ephemeral isolation.",
  },
  {
    title: "4. Tune RAG Hyperparameters",
    description:
      "Open the RAG Settings drawer to switch between Corrective RAG (CRAG), Graph RAG entity exploration, or adjust reranker cutoff thresholds.",
    icon: <Sliders className="w-6 h-6 text-purple-400" />,
    hint: "Experiment with Hybrid Alpha (Dense vs Sparse weighting).",
  },
];

interface DemoGuidedTourProps {
  onComplete?: () => void;
}

export function DemoGuidedTour({ onComplete }: DemoGuidedTourProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const seen = sessionStorage.getItem("titan_sandbox_tour_seen");
    if (!seen) {
      setIsOpen(true);
    }
  }, []);

  const handleNext = () => {
    if (currentStep < TOUR_STEPS.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      handleDismiss();
    }
  };

  const handlePrev = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleDismiss = () => {
    sessionStorage.setItem("titan_sandbox_tour_seen", "true");
    setIsOpen(false);
    onComplete?.();
  };

  if (!isOpen) return null;

  const step = TOUR_STEPS[currentStep];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="tour-title"
    >
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-6 relative">
        <button
          onClick={handleDismiss}
          className="absolute top-4 right-4 p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
          aria-label="Skip tour"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header Indicator */}
        <div className="flex items-center gap-3">
          <div className="p-3 bg-slate-800 rounded-xl border border-slate-700">
            {step.icon}
          </div>
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-indigo-400">
              Interactive Guided Tour ({currentStep + 1} of {TOUR_STEPS.length})
            </div>
            <h2 id="tour-title" className="text-lg font-bold text-slate-100">
              {step.title}
            </h2>
          </div>
        </div>

        {/* Body */}
        <div className="space-y-4">
          <p className="text-sm text-slate-300 leading-relaxed">
            {step.description}
          </p>

          <div className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800 text-xs text-slate-400">
            <span className="font-semibold text-slate-200">Pro Tip: </span>
            {step.hint}
          </div>
        </div>

        {/* Progress Dots & Nav */}
        <div className="flex items-center justify-between pt-2 border-t border-slate-800/80">
          <div className="flex items-center gap-1.5">
            {TOUR_STEPS.map((_, idx) => (
              <div
                key={idx}
                className={`h-1.5 rounded-full transition-all duration-300 ${
                  idx === currentStep
                    ? "w-6 bg-indigo-500"
                    : "w-2 bg-slate-700"
                }`}
              />
            ))}
          </div>

          <div className="flex items-center gap-2">
            {currentStep > 0 && (
              <button
                onClick={handlePrev}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 hover:bg-slate-800 transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Back
              </button>
            )}
            <button
              onClick={handleNext}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/30 transition-all"
            >
              <span>{currentStep === TOUR_STEPS.length - 1 ? "Start Exploring" : "Next"}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
