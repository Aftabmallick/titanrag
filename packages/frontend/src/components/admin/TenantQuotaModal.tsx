"use client";

import React, { useState } from "react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Slider } from "@/components/ui/Slider";
import { Toggle } from "@/components/ui/Toggle";
import { useToast } from "@/components/ui/Toast";
import { ShieldAlert, Users, HardDrive, Database, Zap, RefreshCw, CheckCircle2 } from "lucide-react";

export interface TenantQuotaModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function TenantQuotaModal({ isOpen, onClose }: TenantQuotaModalProps) {
  const { success, info } = useToast();

  const [maxDocs, setMaxDocs] = useState(5000);
  const [maxStorageGb, setMaxStorageGb] = useState(50);
  const [dailyQueryLimit, setDailyQueryLimit] = useState(10000);
  const [cuMonthlyQuota, setCuMonthlyQuota] = useState(25000);
  const [scimEnabled, setScimEnabled] = useState(true);
  const [syncingScim, setSyncingScim] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleSyncScim = () => {
    setSyncingScim(true);
    info("SCIM 2.0 Inbound Sync Triggered", "Pulling directory users and group assignments from IdP...");
    setTimeout(() => {
      setSyncingScim(false);
      success("SCIM Sync Complete", "42 user accounts and 6 security groups synchronized.");
    }, 1500);
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setTimeout(() => {
      setSaving(false);
      success("Tenant Policies Updated", "New quota limits committed to PostgreSQL system config.");
      onClose();
    }, 600);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Tenant Quota & SCIM Identity Governance"
      description="Configure enterprise-wide resource ceilings, FinOps CU caps, and SCIM 2.0 automated provisioning."
      maxWidth="lg"
    >
      <form onSubmit={handleSave} className="space-y-5">
        {/* Quota Limits Grid */}
        <div className="space-y-4">
          <div className="text-xs font-bold text-slate-300 uppercase tracking-wider border-b border-slate-800 pb-1 flex items-center gap-2">
            <HardDrive className="w-3.5 h-3.5 text-sky-400" />
            <span>Resource & Compute Caps</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
                <span>Max Documents Limit</span>
                <span className="font-mono text-sky-400">{maxDocs.toLocaleString()}</span>
              </label>
              <input
                type="number"
                min={100}
                max={50000}
                step={500}
                value={maxDocs}
                onChange={(e) => setMaxDocs(Number(e.target.value))}
                className="w-full px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700 text-xs text-white"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
                <span>Storage Limit (GB)</span>
                <span className="font-mono text-sky-400">{maxStorageGb} GB</span>
              </label>
              <input
                type="number"
                min={5}
                max={500}
                step={5}
                value={maxStorageGb}
                onChange={(e) => setMaxStorageGb(Number(e.target.value))}
                className="w-full px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700 text-xs text-white"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
                <span>Daily Queries Cap</span>
                <span className="font-mono text-indigo-400">{dailyQueryLimit.toLocaleString()}</span>
              </label>
              <input
                type="number"
                min={1000}
                max={100000}
                step={1000}
                value={dailyQueryLimit}
                onChange={(e) => setDailyQueryLimit(Number(e.target.value))}
                className="w-full px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700 text-xs text-white"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
                <span>Monthly Compute Units (CU)</span>
                <span className="font-mono text-amber-400">{cuMonthlyQuota.toLocaleString()} CU</span>
              </label>
              <input
                type="number"
                min={1000}
                max={250000}
                step={5000}
                value={cuMonthlyQuota}
                onChange={(e) => setCuMonthlyQuota(Number(e.target.value))}
                className="w-full px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700 text-xs text-white"
              />
            </div>
          </div>
        </div>

        {/* SCIM 2.0 Directory Governance */}
        <div className="space-y-3 pt-2">
          <div className="text-xs font-bold text-slate-300 uppercase tracking-wider border-b border-slate-800 pb-1 flex items-center gap-2">
            <Users className="w-3.5 h-3.5 text-emerald-400" />
            <span>SCIM 2.0 Enterprise Directory</span>
          </div>

          <div className="p-3.5 rounded-xl border border-slate-800 bg-slate-950/60 flex items-center justify-between">
            <div className="space-y-0.5">
              <div className="text-xs font-bold text-white flex items-center gap-2">
                <span>Inbound SCIM 2.0 Directory Provisioning</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  Active (Okta / Azure AD)
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                Automatically de-provision departed employees and evict cached session JWTs.
              </p>
            </div>
            <Toggle checked={scimEnabled} onChange={setScimEnabled} />
          </div>

          <div className="flex items-center justify-between p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs">
            <span className="text-slate-400">Last IdP Directory Sync: <strong>38 minutes ago</strong></span>
            <Button
              type="button"
              variant="outline"
              size="xs"
              loading={syncingScim}
              onClick={handleSyncScim}
              icon={<RefreshCw className="w-3 h-3 text-sky-400" />}
            >
              Sync Directory Now
            </Button>
          </div>
        </div>

        {/* Modal Actions */}
        <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
          <Button variant="ghost" size="sm" type="button" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button variant="primary" size="sm" type="submit" loading={saving}>
            Save Quota Policies
          </Button>
        </div>
      </form>
    </Modal>
  );
}
