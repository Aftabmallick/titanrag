"use client";

import React, { useEffect, useState } from "react";
import { CreditCard, TrendingUp, AlertTriangle, CheckCircle, Zap, ArrowUp } from "lucide-react";

interface SubscriptionData {
  plan_slug: string;
  subscription_status: string;
  cu_monthly_limit: number;
  cu_used_this_month: number;
  cu_remaining: number;
  cu_percent_used: number;
  current_period_end: string | null;
  billing_email: string | null;
  plan_features: Record<string, unknown>;
}

const PLAN_COLORS: Record<string, string> = {
  FREE: "from-slate-600 to-slate-500",
  PRO: "from-indigo-600 to-violet-600",
  ENTERPRISE: "from-amber-500 to-orange-500",
  SANDBOX: "from-emerald-600 to-teal-600",
};

const PLAN_BADGES: Record<string, string> = {
  FREE: "bg-slate-700 text-slate-300",
  PRO: "bg-indigo-900/60 text-indigo-300 ring-1 ring-indigo-500/30",
  ENTERPRISE: "bg-amber-900/60 text-amber-300 ring-1 ring-amber-500/30",
  SANDBOX: "bg-emerald-900/60 text-emerald-300",
};

export function PlanUsageCard() {
  const [data, setData] = useState<SubscriptionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchSubscription() {
      try {
        const res = await fetch("/api/v1/billing/subscription", {
          headers: { Authorization: `Bearer ${localStorage.getItem("titan_token")}` },
        });
        if (!res.ok) throw new Error("Failed to load subscription");
        const json = await res.json();
        setData(json);
      } catch (err) {
        setError("Could not load billing information");
      } finally {
        setLoading(false);
      }
    }
    fetchSubscription();
  }, []);

  if (loading) {
    return (
      <div className="glass-card rounded-2xl p-6 border border-slate-700/50 animate-pulse">
        <div className="h-6 bg-slate-700 rounded w-1/3 mb-4" />
        <div className="h-4 bg-slate-700/60 rounded w-full mb-2" />
        <div className="h-4 bg-slate-700/60 rounded w-3/4" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="glass-card rounded-2xl p-6 border border-red-800/40 bg-red-950/20">
        <div className="flex items-center gap-2 text-red-400">
          <AlertTriangle className="w-5 h-5" />
          <span className="text-sm">{error}</span>
        </div>
      </div>
    );
  }

  const isOverage = data.cu_percent_used > 100;
  const isWarning = data.cu_percent_used >= 80 && data.cu_percent_used <= 100;
  const progressColor = isOverage
    ? "bg-red-500"
    : isWarning
    ? "bg-amber-500"
    : "bg-gradient-to-r from-indigo-500 to-violet-500";

  const progressWidth = Math.min(data.cu_percent_used, 100);

  const periodEndDate = data.current_period_end
    ? new Date(data.current_period_end).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : null;

  return (
    <div className="glass-card rounded-2xl border border-slate-700/50 overflow-hidden">
      {/* Header gradient */}
      <div className={`bg-gradient-to-r ${PLAN_COLORS[data.plan_slug] || PLAN_COLORS.FREE} p-5`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center backdrop-blur-sm">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="text-xs text-white/60 font-medium uppercase tracking-wider">
                Current Plan
              </p>
              <div className="flex items-center gap-2 mt-0.5">
                <span
                  className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                    PLAN_BADGES[data.plan_slug] || PLAN_BADGES.FREE
                  }`}
                >
                  {data.plan_slug}
                </span>
                {data.subscription_status === "ACTIVE" ? (
                  <CheckCircle className="w-4 h-4 text-emerald-400" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                )}
              </div>
            </div>
          </div>
          {data.plan_slug !== "ENTERPRISE" && (
            <button
              id="billing-upgrade-btn"
              className="flex items-center gap-1.5 bg-white/15 hover:bg-white/25 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition-all duration-200 border border-white/20 hover:border-white/30"
              onClick={() => (window.location.href = "/admin/billing")}
            >
              <ArrowUp className="w-3 h-3" />
              Upgrade
            </button>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="p-5 space-y-4">
        {/* CU Usage */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-slate-400">Compute Units Used</span>
            <div className="flex items-center gap-2">
              {isOverage && (
                <span className="text-xs text-red-400 font-semibold">
                  +{Math.round(data.cu_percent_used - 100)}% over limit
                </span>
              )}
              <span
                className={`text-xs font-bold ${
                  isOverage ? "text-red-400" : isWarning ? "text-amber-400" : "text-slate-300"
                }`}
              >
                {data.cu_used_this_month.toLocaleString()} / {data.cu_monthly_limit.toLocaleString()} CU
              </span>
            </div>
          </div>

          {/* Progress bar */}
          <div className="relative h-2.5 bg-slate-700/60 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ease-out ${progressColor}`}
              style={{ width: `${progressWidth}%` }}
            />
            {isOverage && (
              <div className="absolute inset-0 animate-shimmer-bg" />
            )}
          </div>

          <div className="flex justify-between mt-1.5">
            <span className="text-xs text-slate-500">{data.cu_percent_used.toFixed(1)}% used</span>
            <span className="text-xs text-slate-500">
              {data.cu_remaining.toLocaleString()} CU remaining
            </span>
          </div>
        </div>

        {/* Billing period */}
        {periodEndDate && (
          <div className="flex items-center justify-between py-3 border-t border-slate-700/50">
            <div className="flex items-center gap-2 text-slate-400">
              <CreditCard className="w-4 h-4" />
              <span className="text-xs">Billing period ends</span>
            </div>
            <span className="text-xs font-semibold text-slate-300">{periodEndDate}</span>
          </div>
        )}

        {/* Status banner for payment failure */}
        {data.subscription_status === "READ_ONLY" && (
          <div className="flex items-start gap-2.5 p-3 bg-red-950/40 border border-red-800/40 rounded-xl">
            <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-red-300">Payment Failed — Read-Only Mode</p>
              <p className="text-xs text-red-400/80 mt-0.5">
                Ingestion is paused. Queries still work. Update your payment method to restore full access.
              </p>
              <button
                id="billing-update-payment-btn"
                className="mt-2 text-xs text-red-300 underline hover:text-red-200 transition-colors"
                onClick={() => {
                  /* Open Stripe Customer Portal */
                }}
              >
                Update payment method →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
