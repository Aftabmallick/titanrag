"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Globe,
  Upload,
  Palette,
  Eye,
  Loader2,
  CheckCircle,
  AlertTriangle,
  Link,
  Copy,
  RefreshCw,
} from "lucide-react";

interface BrandConfig {
  company_name: string;
  primary_color: string;
  accent_color: string;
  custom_domain: string | null;
  from_email: string | null;
  from_name: string | null;
  logo_light_url: string | null;
  logo_dark_url: string | null;
  favicon_url: string | null;
  domain_verified: boolean;
}

const DEFAULT_CONFIG: BrandConfig = {
  company_name: "TitanRAG",
  primary_color: "#6366f1",
  accent_color: "#8b5cf6",
  custom_domain: null,
  from_email: null,
  from_name: null,
  logo_light_url: null,
  logo_dark_url: null,
  favicon_url: null,
  domain_verified: false,
};

function ColorPicker({
  label,
  value,
  onChange,
  id,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  id: string;
}) {
  return (
    <div>
      <label htmlFor={id} className="block text-xs font-medium text-slate-400 mb-1.5">
        {label}
      </label>
      <div className="flex items-center gap-3">
        <div className="relative">
          <input
            id={id}
            type="color"
            value={value}
            onChange={(e) => onChange(e.target.value.toUpperCase())}
            className="absolute inset-0 opacity-0 cursor-pointer w-10 h-10"
            aria-label={label}
          />
          <div
            className="w-10 h-10 rounded-xl border-2 border-slate-600 cursor-pointer shadow-inner transition-transform hover:scale-105"
            style={{ backgroundColor: value }}
          />
        </div>
        <input
          type="text"
          value={value}
          onChange={(e) => {
            const v = e.target.value.toUpperCase();
            if (/^#[0-9A-F]{0,6}$/.test(v)) onChange(v);
          }}
          maxLength={7}
          className="flex-1 bg-slate-800/60 border border-slate-700/60 rounded-xl px-3 py-2 text-sm font-mono text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
          aria-label={`${label} hex value`}
        />
      </div>
    </div>
  );
}

function LogoDropzone({
  label,
  assetType,
  currentUrl,
  onUploaded,
}: {
  label: string;
  assetType: string;
  currentUrl: string | null;
  onUploaded: (url: string) => void;
}) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File) {
    setUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`/api/v1/admin/brand/assets?asset_type=${assetType}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("titan_token")}` },
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail?.message || "Upload failed");
      }
      const { url } = await res.json();
      onUploaded(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div>
      <p className="text-xs font-medium text-slate-400 mb-2">{label}</p>
      <label
        className={`block cursor-pointer border-2 border-dashed rounded-2xl p-6 text-center transition-all duration-200 ${
          uploading
            ? "border-indigo-500/40 bg-indigo-950/20"
            : "border-slate-700/60 hover:border-slate-600 hover:bg-slate-800/30"
        }`}
        id={`brand-${assetType}-upload`}
        aria-label={`Upload ${label}`}
      >
        <input
          type="file"
          accept="image/png,image/jpeg,image/svg+xml,image/webp"
          className="sr-only"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
          }}
        />

        {uploading ? (
          <div className="flex flex-col items-center gap-2 text-indigo-400">
            <Loader2 className="w-8 h-8 animate-spin" />
            <span className="text-xs">Uploading...</span>
          </div>
        ) : currentUrl ? (
          <div className="flex flex-col items-center gap-2">
            <img
              src={currentUrl}
              alt={label}
              className="h-12 max-w-32 object-contain rounded"
            />
            <span className="text-xs text-slate-400">Click to replace</span>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 text-slate-500">
            <Upload className="w-8 h-8" />
            <span className="text-xs">Drop image or click to upload</span>
            <span className="text-xs text-slate-600">PNG, SVG, JPG · max 2MB</span>
          </div>
        )}
      </label>
      {error && <p className="text-xs text-red-400 mt-1">{error}</p>}
    </div>
  );
}

export function BrandConfigEditor() {
  const [config, setConfig] = useState<BrandConfig>(DEFAULT_CONFIG);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<{
    verified: boolean;
    message: string;
    token: string | null;
  } | null>(null);

  const token = () => localStorage.getItem("titan_token") || "";

  useEffect(() => {
    fetch("/api/v1/admin/brand", {
      headers: { Authorization: `Bearer ${token()}` },
    })
      .then((r) => r.json())
      .then((data) => {
        setConfig((prev) => ({ ...prev, ...data }));
      })
      .finally(() => setLoading(false));
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setSaved(false);
    try {
      const res = await fetch("/api/v1/admin/brand", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token()}`,
        },
        body: JSON.stringify({
          company_name: config.company_name,
          primary_color: config.primary_color,
          accent_color: config.accent_color,
          custom_domain: config.custom_domain || null,
          from_email: config.from_email || null,
          from_name: config.from_name || null,
        }),
      });
      if (res.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
      }
    } finally {
      setSaving(false);
    }
  }, [config]);

  const handleVerifyDomain = useCallback(async () => {
    setVerifying(true);
    setVerifyResult(null);
    try {
      const res = await fetch("/api/v1/admin/brand/domain/verify", {
        method: "POST",
        headers: { Authorization: `Bearer ${token()}` },
      });
      const data = await res.json();
      setVerifyResult({
        verified: data.verified,
        message: data.message,
        token: data.verification_token,
      });
    } finally {
      setVerifying(false);
    }
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-16 bg-slate-800/40 rounded-2xl animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Live preview strip */}
      <div
        className="rounded-2xl p-4 border border-slate-700/50 flex items-center gap-4"
        style={{
          background: `linear-gradient(135deg, ${config.primary_color}15, ${config.accent_color}10)`,
          borderColor: `${config.primary_color}30`,
        }}
        aria-label="Brand preview"
      >
        <div className="flex items-center gap-3">
          {config.logo_light_url ? (
            <img
              src={config.logo_light_url}
              alt="Brand logo preview"
              className="h-9 max-w-[120px] object-contain"
            />
          ) : (
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center text-white text-sm font-bold"
              style={{ background: `linear-gradient(135deg, ${config.primary_color}, ${config.accent_color})` }}
            >
              {config.company_name[0]?.toUpperCase()}
            </div>
          )}
          <span className="font-semibold text-slate-100">{config.company_name}</span>
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          <Eye className="w-4 h-4 text-slate-500" />
          <span className="text-xs text-slate-500">Live Preview</span>
        </div>
      </div>

      {/* Section: Company info */}
      <section aria-labelledby="brand-company-section">
        <h3 id="brand-company-section" className="text-sm font-semibold text-slate-300 mb-4">
          Company Identity
        </h3>
        <div className="space-y-4">
          <div>
            <label htmlFor="brand-company-name" className="block text-xs font-medium text-slate-400 mb-1.5">
              Company Name
            </label>
            <input
              id="brand-company-name"
              type="text"
              value={config.company_name}
              onChange={(e) => setConfig((c) => ({ ...c, company_name: e.target.value }))}
              maxLength={128}
              className="w-full bg-slate-800/60 border border-slate-700/60 rounded-xl px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
              placeholder="Your Company"
            />
          </div>
        </div>
      </section>

      {/* Section: Brand colors */}
      <section aria-labelledby="brand-colors-section">
        <div className="flex items-center gap-2 mb-4">
          <Palette className="w-4 h-4 text-slate-400" />
          <h3 id="brand-colors-section" className="text-sm font-semibold text-slate-300">
            Brand Colors
          </h3>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <ColorPicker
            id="brand-primary-color"
            label="Primary Color"
            value={config.primary_color}
            onChange={(v) => setConfig((c) => ({ ...c, primary_color: v }))}
          />
          <ColorPicker
            id="brand-accent-color"
            label="Accent Color"
            value={config.accent_color}
            onChange={(v) => setConfig((c) => ({ ...c, accent_color: v }))}
          />
        </div>
      </section>

      {/* Section: Logo uploads */}
      <section aria-labelledby="brand-logos-section">
        <h3 id="brand-logos-section" className="text-sm font-semibold text-slate-300 mb-4">
          Brand Assets
        </h3>
        <div className="grid grid-cols-3 gap-4">
          <LogoDropzone
            label="Logo (Light Mode)"
            assetType="logo_light"
            currentUrl={config.logo_light_url}
            onUploaded={(url) => setConfig((c) => ({ ...c, logo_light_url: url }))}
          />
          <LogoDropzone
            label="Logo (Dark Mode)"
            assetType="logo_dark"
            currentUrl={config.logo_dark_url}
            onUploaded={(url) => setConfig((c) => ({ ...c, logo_dark_url: url }))}
          />
          <LogoDropzone
            label="Favicon"
            assetType="favicon"
            currentUrl={config.favicon_url}
            onUploaded={(url) => setConfig((c) => ({ ...c, favicon_url: url }))}
          />
        </div>
      </section>

      {/* Section: Custom domain */}
      <section aria-labelledby="brand-domain-section">
        <div className="flex items-center gap-2 mb-4">
          <Globe className="w-4 h-4 text-slate-400" />
          <h3 id="brand-domain-section" className="text-sm font-semibold text-slate-300">
            Custom Domain
          </h3>
          {config.domain_verified && (
            <span className="inline-flex items-center gap-1 text-xs text-emerald-400 bg-emerald-900/30 px-2 py-0.5 rounded-full ring-1 ring-emerald-700/40">
              <CheckCircle className="w-3 h-3" />
              Verified
            </span>
          )}
        </div>
        <div className="space-y-3">
          <input
            id="brand-custom-domain"
            type="text"
            value={config.custom_domain || ""}
            onChange={(e) => setConfig((c) => ({ ...c, custom_domain: e.target.value || null }))}
            placeholder="app.yourcompany.com"
            className="w-full bg-slate-800/60 border border-slate-700/60 rounded-xl px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
          />

          {config.custom_domain && !config.domain_verified && (
            <button
              id="brand-verify-domain-btn"
              onClick={handleVerifyDomain}
              disabled={verifying}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium text-indigo-300 border border-indigo-700/50 hover:bg-indigo-900/30 transition-all disabled:opacity-50"
            >
              {verifying ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4" />
              )}
              Check DNS Verification
            </button>
          )}

          {verifyResult && (
            <div
              className={`p-3 rounded-xl border text-sm ${
                verifyResult.verified
                  ? "bg-emerald-950/30 border-emerald-800/40 text-emerald-300"
                  : "bg-amber-950/30 border-amber-800/40 text-amber-300"
              }`}
            >
              <p>{verifyResult.message}</p>
              {verifyResult.token && (
                <div className="mt-2 p-2 bg-slate-900/60 rounded-lg font-mono text-xs flex items-center gap-2">
                  <Link className="w-3 h-3 text-slate-500 flex-shrink-0" />
                  <span className="break-all">{verifyResult.token}</span>
                  <button
                    onClick={() => navigator.clipboard.writeText(verifyResult.token!)}
                    className="ml-auto flex-shrink-0 text-slate-500 hover:text-slate-300"
                    aria-label="Copy verification token"
                  >
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      {/* Save button */}
      <div className="flex items-center justify-between pt-4 border-t border-slate-700/50">
        {saved && (
          <span className="flex items-center gap-2 text-sm text-emerald-400">
            <CheckCircle className="w-4 h-4" />
            Brand settings saved
          </span>
        )}
        <div className="ml-auto">
          <button
            id="brand-save-btn"
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold bg-gradient-to-r from-indigo-600 to-violet-600 text-white hover:from-indigo-500 hover:to-violet-500 transition-all shadow-lg shadow-indigo-500/20 disabled:opacity-50"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            {saving ? "Saving..." : "Save Brand Settings"}
          </button>
        </div>
      </div>
    </div>
  );
}
