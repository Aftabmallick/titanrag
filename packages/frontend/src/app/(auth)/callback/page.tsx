"use client";

import React, { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/components/ui/Toast";
import { Loader2, CheckCircle2, AlertCircle, ShieldCheck } from "lucide-react";

function OAuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { refreshUser, refreshWorkspaces } = useAuth();
  const { success, error: toastError } = useToast();

  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    async function exchangeOAuthCode() {
      const code = searchParams.get("code");
      const state = searchParams.get("state");
      const provider = searchParams.get("provider") || "google";
      const errorParam = searchParams.get("error");

      if (errorParam) {
        setStatus("error");
        const msg = searchParams.get("error_description") || errorParam;
        setErrorMessage(msg);
        toastError("OAuth Sign-In Failed", msg);
        return;
      }

      if (!code) {
        setStatus("error");
        setErrorMessage("Missing authorization code in OAuth callback.");
        return;
      }

      try {
        const res = await api.oauthCallback(provider, code, state || "");
        if (res.access_token) {
          localStorage.setItem("titan_token", res.access_token);
          document.cookie = `titan_token=${encodeURIComponent(res.access_token)}; path=/; max-age=604800; SameSite=Lax`;
          await refreshUser();
          await refreshWorkspaces();
          setStatus("success");
          success("OAuth Authentication Complete", "Enterprise identity linked successfully.");
          setTimeout(() => {
            router.push("/");
          }, 800);
        } else {
          throw new Error("Did not receive access_token from authentication server.");
        }
      } catch (err: any) {
        setStatus("error");
        setErrorMessage(err.message || "Failed to exchange OAuth authorization code.");
        toastError("Authentication Error", err.message || "OAuth exchange failed.");
      }
    }

    exchangeOAuthCode();
  }, [searchParams, router, refreshUser, refreshWorkspaces, success, toastError]);

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-6 text-slate-100">
      <div className="max-w-md w-full p-8 rounded-2xl border border-slate-800 bg-slate-900/80 shadow-2xl backdrop-blur-xl text-center space-y-6">
        <div className="flex items-center justify-center mx-auto">
          {status === "loading" && (
            <div className="w-14 h-14 rounded-2xl bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400">
              <Loader2 className="w-7 h-7 animate-spin" />
            </div>
          )}
          {status === "success" && (
            <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <CheckCircle2 className="w-7 h-7" />
            </div>
          )}
          {status === "error" && (
            <div className="w-14 h-14 rounded-2xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-center text-rose-400">
              <AlertCircle className="w-7 h-7" />
            </div>
          )}
        </div>

        <div className="space-y-1.5">
          <h2 className="text-lg font-bold text-white tracking-tight">
            {status === "loading" && "Authenticating with Enterprise IdP..."}
            {status === "success" && "Identity Confirmed & Linked"}
            {status === "error" && "OAuth Verification Failed"}
          </h2>
          <p className="text-xs text-slate-400 leading-relaxed">
            {status === "loading" && "Validating OAuth state, exchanging authorization code, and issuing session JWT..."}
            {status === "success" && "Redirecting to your isolated enterprise workspace..."}
            {status === "error" && (errorMessage || "An error occurred during social login.")}
          </p>
        </div>

        {status === "error" && (
          <button
            onClick={() => router.push("/login")}
            className="w-full py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-white transition-colors"
          >
            Return to Login
          </button>
        )}
      </div>
    </div>
  );
}

export default function OAuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-6 text-slate-100">
          <div className="w-14 h-14 rounded-2xl bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400">
            <Loader2 className="w-7 h-7 animate-spin" />
          </div>
        </div>
      }
    >
      <OAuthCallbackContent />
    </Suspense>
  );
}
