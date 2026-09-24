"use client";

import React, { useState } from "react";
import { X, Zap, Check, Shield, Star, Loader2 } from "lucide-react";

interface Plan {
  slug: string;
  name: string;
  price: string;
  period: string;
  cu: string;
  workspaces: string;
  documents: string;
  features: string[];
  highlight: boolean;
  gradient: string;
  badge?: string;
}

const PLANS: Plan[] = [
  {
    slug: "FREE",
    name: "Free",
    price: "$0",
    period: "forever",
    cu: "100 CU / month",
    workspaces: "1 workspace",
    documents: "50 documents",
    highlight: false,
    gradient: "from-slate-700 to-slate-600",
    features: [
      "Hybrid semantic search",
      "PDF, DOCX, TXT support",
      "Basic RAG pipeline",
      "Community support",
    ],
  },
  {
    slug: "PRO",
    name: "Pro",
    price: "$49",
    period: "per month",
    cu: "5,000 CU / month",
    workspaces: "10 workspaces",
    documents: "5,000 documents",
    highlight: true,
    gradient: "from-indigo-600 to-violet-600",
    badge: "Most Popular",
    features: [
      "Everything in Free",
      "ColPali visual embeddings",
      "Graph RAG (Neo4j)",
      "SAML SSO",
      "A/B testing & PromptOps",
      "Priority support",
    ],
  },
  {
    slug: "ENTERPRISE",
    name: "Enterprise",
    price: "Custom",
    period: "contact us",
    cu: "Unlimited CU",
    workspaces: "Unlimited",
    documents: "Unlimited",
    highlight: false,
    gradient: "from-amber-600 to-orange-600",
    badge: "Enterprise",
    features: [
      "Everything in Pro",
      "BYOK (Bring Your Own Key)",
      "Data residency (EU/US/APAC)",
      "SCIM provisioning",
      "SLA guarantee",
      "Dedicated support",
      "White-label branding",
    ],
  },
];

interface PlanUpgradeModalProps {
  currentPlan: string;
  isOpen: boolean;
  onClose: () => void;
}

export function PlanUpgradeModal({
  currentPlan,
  isOpen,
  onClose,
}: PlanUpgradeModalProps) {
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  async function handleUpgrade(planSlug: string) {
    if (planSlug === "ENTERPRISE") {
      window.open("mailto:enterprise@titanrag.io?subject=Enterprise Inquiry", "_blank");
      return;
    }

    setLoading(planSlug);
    setError(null);

    try {
      const res = await fetch("/api/v1/billing/checkout", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("titan_token")}`,
        },
        body: JSON.stringify({
          plan_slug: planSlug,
          success_url: `${window.location.origin}/admin/billing?upgraded=true`,
          cancel_url: `${window.location.origin}/admin/billing`,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail?.message || "Failed to create checkout session");
      }

      const { checkout_url } = await res.json();
      if (checkout_url) {
        window.location.href = checkout_url;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="plan-upgrade-modal-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-slate-950/80 backdrop-blur-md"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div className="relative z-10 w-full max-w-4xl mx-4 glass-card rounded-2xl border border-slate-700/60 shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-slate-700/50">
          <div>
            <h2
              id="plan-upgrade-modal-title"
              className="text-xl font-bold text-slate-100"
            >
              Upgrade Your Plan
            </h2>
            <p className="text-sm text-slate-400 mt-0.5">
              Scale your RAG platform with more Compute Units and features
            </p>
          </div>
          <button
            id="plan-upgrade-modal-close"
            onClick={onClose}
            className="w-9 h-9 flex items-center justify-center rounded-xl text-slate-400 hover:text-slate-100 hover:bg-slate-700/60 transition-all"
            aria-label="Close plan upgrade modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Error banner */}
        {error && (
          <div className="mx-6 mt-4 p-3 bg-red-950/50 border border-red-800/40 rounded-xl text-sm text-red-300">
            {error}
          </div>
        )}

        {/* Plans grid */}
        <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          {PLANS.map((plan) => {
            const isCurrent = plan.slug === currentPlan;
            const isHighlighted = plan.highlight;

            return (
              <div
                key={plan.slug}
                className={`relative rounded-2xl border transition-all duration-200 overflow-hidden ${
                  isHighlighted
                    ? "border-indigo-500/50 ring-1 ring-indigo-500/20 shadow-lg shadow-indigo-500/10"
                    : "border-slate-700/50"
                } ${isCurrent ? "opacity-60" : ""}`}
              >
                {/* Badge */}
                {plan.badge && (
                  <div
                    className={`absolute top-3 right-3 text-xs font-bold px-2.5 py-0.5 rounded-full bg-gradient-to-r ${plan.gradient} text-white`}
                  >
                    {plan.badge}
                  </div>
                )}

                {/* Plan header */}
                <div className={`bg-gradient-to-br ${plan.gradient} p-5`}>
                  <p className="text-sm font-bold text-white/80">{plan.name}</p>
                  <div className="flex items-baseline gap-1 mt-1">
                    <span className="text-3xl font-black text-white">{plan.price}</span>
                    <span className="text-sm text-white/60">/{plan.period}</span>
                  </div>
                </div>

                {/* Features */}
                <div className="p-5 bg-slate-800/40 space-y-3">
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2 text-xs text-slate-300">
                      <Zap className="w-3.5 h-3.5 text-amber-400" />
                      <span className="font-semibold">{plan.cu}</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                      <Shield className="w-3.5 h-3.5 text-indigo-400" />
                      <span>{plan.workspaces}</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                      <Star className="w-3.5 h-3.5 text-violet-400" />
                      <span>{plan.documents}</span>
                    </div>
                  </div>

                  <div className="border-t border-slate-700/50 pt-3 space-y-1.5">
                    {plan.features.map((feature, i) => (
                      <div key={i} className="flex items-start gap-2">
                        <Check className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0 mt-0.5" />
                        <span className="text-xs text-slate-400">{feature}</span>
                      </div>
                    ))}
                  </div>

                  <button
                    id={`plan-upgrade-${plan.slug.toLowerCase()}-btn`}
                    onClick={() => handleUpgrade(plan.slug)}
                    disabled={isCurrent || loading === plan.slug}
                    className={`w-full mt-4 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 ${
                      isCurrent
                        ? "bg-slate-700/50 text-slate-500 cursor-not-allowed"
                        : isHighlighted
                        ? "bg-gradient-to-r from-indigo-600 to-violet-600 text-white hover:from-indigo-500 hover:to-violet-500 shadow-md hover:shadow-indigo-500/20"
                        : "bg-slate-700 text-slate-100 hover:bg-slate-600"
                    }`}
                    aria-label={
                      isCurrent
                        ? `${plan.name} is your current plan`
                        : `Upgrade to ${plan.name}`
                    }
                  >
                    {loading === plan.slug ? (
                      <span className="flex items-center justify-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Redirecting...
                      </span>
                    ) : isCurrent ? (
                      "Current Plan"
                    ) : plan.slug === "ENTERPRISE" ? (
                      "Contact Sales"
                    ) : (
                      `Upgrade to ${plan.name}`
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        <div className="px-6 pb-5 text-center">
          <p className="text-xs text-slate-500">
            Payments processed securely via Stripe. Cancel anytime.{" "}
            <a href="#" className="text-indigo-400 hover:text-indigo-300 underline">
              Terms of Service
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
