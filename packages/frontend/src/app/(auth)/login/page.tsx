"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { AuthCard } from "@/components/auth/AuthCard";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/components/ui/Toast";
import { Mail, Lock, Sparkles, AlertCircle } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { login, demoLogin } = useAuth();
  const { success, error: toastError } = useToast();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setErrorMessage("Please fill in both email and password.");
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    try {
      await login(email, password);
      success("Welcome back!", "Authentication successful.");
      router.push("/");
    } catch (err: any) {
      setErrorMessage(err.message || "Invalid credentials or account locked.");
      toastError("Authentication Failed", err.message || "Please check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  const handleDemoLogin = async () => {
    setDemoLoading(true);
    setErrorMessage(null);
    try {
      await demoLogin();
      success("Authenticated as Administrator", "Provisioned sandbox tenant session.");
      router.push("/");
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to initialize demo credentials.");
      toastError("Demo Login Failed", err.message);
    } finally {
      setDemoLoading(false);
    }
  };

  return (
    <AuthCard
      title="Sign in to TitanRAG"
      subtitle="Access your secure, isolated enterprise knowledge workspaces"
      footerText="Don't have an enterprise account?"
      footerLinkText="Create Tenant"
      footerLinkHref="/register"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {errorMessage && (
          <div className="flex items-center gap-2.5 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        <Input
          label="Work Email"
          type="email"
          placeholder="name@company.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          leftIcon={<Mail className="w-4 h-4" />}
          required
        />

        <Input
          label="Password"
          type="password"
          placeholder="••••••••••••"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          leftIcon={<Lock className="w-4 h-4" />}
          required
        />

        <Button
          type="submit"
          variant="primary"
          className="w-full"
          loading={loading}
          disabled={demoLoading}
        >
          Sign In
        </Button>
      </form>

      <div className="relative flex py-2 items-center">
        <div className="flex-grow border-t border-slate-800" />
        <span className="flex-shrink mx-3 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
          Or Quick Access
        </span>
        <div className="flex-grow border-t border-slate-800" />
      </div>

      <div className="space-y-2.5">
        <Button
          type="button"
          variant="secondary"
          className="w-full text-xs font-semibold py-2.5"
          onClick={handleDemoLogin}
          loading={demoLoading}
          disabled={loading}
          icon={<Sparkles className="w-4 h-4 text-sky-400" />}
        >
          Sign In as Admin (Instant Sandbox)
        </Button>

        <div className="grid grid-cols-2 gap-2.5 pt-1">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => (window.location.href = "/api/v1/auth/oauth/google")}
          >
            Google SSO
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => (window.location.href = "/api/v1/auth/oauth/github")}
          >
            GitHub SSO
          </Button>
        </div>
      </div>
    </AuthCard>
  );
}
