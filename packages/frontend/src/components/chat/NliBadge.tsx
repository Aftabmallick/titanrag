import React from "react";
import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

export interface NliBadgeProps {
  status?: "VERIFIED" | "NEUTRAL" | "CONTRADICTED" | string;
  score?: number | null;
  className?: string;
  showTooltip?: boolean;
}

export const NliBadge: React.FC<NliBadgeProps> = ({
  status = "VERIFIED",
  score,
  className,
}) => {
  const hasScore = score !== null && score !== undefined;
  const isVerified = status === "VERIFIED" || (!status && (!hasScore || score >= 0.7));
  const isContradicted = status === "CONTRADICTED" || (hasScore && score < 0.4);
  const isNeutral = !isVerified && !isContradicted;

  const percent = hasScore ? Math.round(score * 100) : null;

  return (
    <div
      title={
        isVerified
          ? `NLI Grounding: Verified Entailment (${percent ?? 100}%)`
          : isContradicted
          ? `NLI Grounding: Contradiction Detected (${percent ?? 0}%)`
          : `NLI Grounding: Neutral / Insufficient Evidence (${percent ?? 50}%)`
      }
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border transition-all cursor-default select-none",
        isVerified && "bg-emerald-500/10 border-emerald-500/30 text-emerald-400 shadow-sm shadow-emerald-500/5",
        isContradicted && "bg-rose-500/10 border-rose-500/30 text-rose-400 shadow-sm shadow-rose-500/5",
        isNeutral && "bg-amber-500/10 border-amber-500/30 text-amber-400 shadow-sm shadow-amber-500/5",
        className
      )}
    >
      {isVerified && <CheckCircle2 className="w-3 h-3 text-emerald-400" />}
      {isContradicted && <XCircle className="w-3 h-3 text-rose-400" />}
      {isNeutral && <AlertTriangle className="w-3 h-3 text-amber-400" />}

      <span>
        {isVerified ? "NLI Verified" : isContradicted ? "Contradiction" : "NLI Neutral"}
        {percent !== null ? ` (${percent}%)` : ""}
      </span>
    </div>
  );
};
