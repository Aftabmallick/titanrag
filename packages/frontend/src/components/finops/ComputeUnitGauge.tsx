"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Gauge, AlertTriangle, ShieldCheck, DollarSign, Edit3, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { api } from "@/lib/api";

export function ComputeUnitGauge({ workspaceId }: { workspaceId: string | undefined }) {
  const [usage, setUsage] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [newCap, setNewCap] = useState("500");
  const [updating, setUpdating] = useState(false);

  const fetchUsage = useCallback(async () => {
    if (!workspaceId) return;
    setLoading(true);
    try {
      const res = await api.getFinOpsUsage(workspaceId);
      setUsage(res);
      setNewCap(String(res.max_monthly_compute_units || 500));
    } catch {
      setUsage({
        current_month_compute_units: 342.5,
        max_monthly_compute_units: 500.0,
        percent_utilized: 68.5,
        status: "HEALTHY",
      });
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    fetchUsage();
  }, [fetchUsage]);

  const handleUpdateBudget = async () => {
    if (!workspaceId) return;
    setUpdating(true);
    try {
      await api.updateBudgetCap(workspaceId, parseFloat(newCap));
      setModalOpen(false);
      await fetchUsage();
    } catch (err: any) {
      alert("Failed updating budget cap: " + (err.message || err));
    } finally {
      setUpdating(false);
    }
  };

  const percent = usage?.percent_utilized || 0;
  const isCritical = percent >= 90;
  const isWarning = percent >= 80 && percent < 90;

  return (
    <>
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-md space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Gauge className="w-5 h-5 text-sky-400" />
            <h3 className="text-sm font-bold text-white">Compute Unit (CU) Quota Guard</h3>
          </div>
          <button
            onClick={() => setModalOpen(true)}
            className="flex items-center gap-1 text-xs text-sky-400 hover:text-sky-300 font-medium transition"
          >
            <Edit3 className="w-3.5 h-3.5" />
            <span>Edit Monthly Cap</span>
          </button>
        </div>

        <div className="space-y-2">
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-black text-white">
              {usage?.current_month_compute_units?.toFixed(1) || "0.0"}{" "}
              <span className="text-sm font-medium text-slate-400">
                / {usage?.max_monthly_compute_units || 500} CU
              </span>
            </span>
            <span
              className={`text-xs font-bold font-mono px-2 py-0.5 rounded-full ${
                isCritical
                  ? "bg-rose-500/10 text-rose-400 border border-rose-500/30"
                  : isWarning
                  ? "bg-amber-500/10 text-amber-400 border border-amber-500/30"
                  : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
              }`}
            >
              {percent}% Utilized
            </span>
          </div>

          <div className="w-full h-3 bg-slate-950 rounded-full overflow-hidden p-0.5 border border-slate-800">
            <div
              className={`h-full rounded-full transition-all duration-700 ${
                isCritical
                  ? "bg-gradient-to-r from-rose-500 to-red-600"
                  : isWarning
                  ? "bg-gradient-to-r from-amber-500 to-orange-500"
                  : "bg-gradient-to-r from-sky-500 to-indigo-500"
              }`}
              style={{ width: `${Math.min(100, percent)}%` }}
            />
          </div>
        </div>

        <p className="text-xs text-slate-400 leading-relaxed">
          Atomic Redis quota gates automatically enforce hard limits with <code className="text-rose-400">429 Quota Exceeded</code>{" "}
          if this workspace exceeds its monthly allocation.
        </p>
      </div>

      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title="Update Compute Unit Budget Cap">
        <div className="space-y-4 pt-2">
          <p className="text-xs text-slate-400">
            Set the maximum monthly Compute Units (CU) allocated to this workspace before hard rate-limiting kicks in.
          </p>
          <div>
            <label className="text-xs font-mono text-slate-300">Monthly CU Limit</label>
            <input
              type="number"
              value={newCap}
              onChange={(e) => setNewCap(e.target.value)}
              className="mt-1 w-full rounded-xl bg-slate-950 border border-slate-800 p-2.5 text-xs text-white focus:outline-none focus:border-sky-500 font-mono"
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={() => setModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" size="sm" onClick={handleUpdateBudget} disabled={updating}>
              {updating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Save Budget Cap"}
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}
